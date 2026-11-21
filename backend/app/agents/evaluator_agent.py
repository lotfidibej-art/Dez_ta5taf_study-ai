import logging
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.db.migrations import get_db_connection
from app.orchestrator.graph import execute_turn
from app.orchestrator.graph_utils import get_next_unlocked_concept
from app.schemas.contracts import (
    DiagnosticAnswer,
    DiagnosticEvaluationItem,
    DiagnosticEvaluationResponse,
    DiagnosticQuestion,
    SessionState,
)
from app.services.llm_client import GeminiLLMClient, get_llm_client

logger = logging.getLogger(__name__)


class LLMAnswerEvaluation(BaseModel):
    factual_accuracy: float = Field(
        ..., ge=0.0, le=1.0, description="Factual correctness of the response from 0.0 to 1.0"
    )
    causal_depth: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Depth of causal reasoning beyond surface keyword recall from 0.0 to 1.0",
    )
    feedback: str = Field(..., description="Actionable pedagogical feedback for this answer")
    identified_misconception: Optional[str] = Field(
        None,
        description="Specific conceptual error, false assumption, or fallacy detected in the answer",
    )


class LLMBatchEvaluationResult(BaseModel):
    evaluations: List[LLMAnswerEvaluation]
    overall_summary: str = Field(
        ..., description="Holistic summary of the student's baseline mental model"
    )


def evaluate_diagnostic_submission(
    session: SessionState,
    questions: List[DiagnosticQuestion],
    answers: List[DiagnosticAnswer],
    llm: Optional[GeminiLLMClient] = None,
) -> DiagnosticEvaluationResponse:
    """Agent 3 (Diagnostic & Baseline Evaluator):

    Evaluates student diagnostic responses using Gemini 3.8 Flash (reasoning tier),
    fuses factual accuracy and causal depth into an initial mastery score, updates node statuses,
    appends detected misconceptions, sets active_concept_id via topological progression,
    and executes the LangGraph state machine to select the initial pedagogical UI component.
    """
    client = llm or get_llm_client()

    q_map = {q.question_id: q for q in questions}
    concept_map = {n.concept_id: n for n in session.concept_graph}

    # Fetch relevant source chunks for tested concepts from PostgreSQL
    source_context_snippets = []
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                tested_ids = [a.concept_id for a in answers]
                if tested_ids:
                    cur.execute(
                        """
                        SELECT concept_id, content, source_name, source_location 
                        FROM resource_chunks 
                        WHERE session_id = %s AND concept_id = ANY(%s)
                        LIMIT 6
                        """,
                        (session.session_id, tested_ids),
                    )
                    for row in cur.fetchall():
                        source_context_snippets.append(
                            f"[{row[2]} - {row[3]} for {row[0]}]:\n{row[1]}"
                        )
    except Exception as e:
        logger.warning("Could not fetch source chunks for evaluation: %s", e)

    context_str = (
        "\n\n".join(source_context_snippets)[:6000]
        if source_context_snippets
        else "No external textbook chunks available. Grade based on rigorous domain ground truth."
    )

    eval_items_prompt = []
    for i, ans in enumerate(answers):
        q = q_map.get(ans.question_id)
        q_text = q.question_text if q else "General diagnostic question"
        c_title = q.concept_title if q else ans.concept_id
        eval_items_prompt.append(
            f"Question {i + 1} (Concept: {c_title} [{ans.concept_id}]):\n"
            f"Prompt: {q_text}\n"
            f"Student Answer: \"{ans.answer_text}\""
        )

    prompt = (
        f"Domain: {session.domain}\n"
        f"Primary Topic: {session.topic_title}\n\n"
        f"SOURCE MATERIAL CONTEXT:\n{context_str}\n\n"
        "STUDENT DIAGNOSTIC SUBMISSION:\n"
        + "\n\n".join(eval_items_prompt)
        + "\n\n"
        "Evaluate each of the 3 student answers independently:\n"
        "1. factual_accuracy (0.0 to 1.0): Truth value against domain facts.\n"
        "2. causal_depth (0.0 to 1.0): Did the student explain WHY the mechanism functions, or merely parrot buzzwords?\n"
        "3. feedback: A constructive 1-2 sentence assessment.\n"
        "4. identified_misconception: If an inversion or fallacy is present, extract it as a short tag (e.g., 'CONFUSED_STACK_WITH_HEAP'). Otherwise null."
    )

    system_instruction = (
        "You are Agent 3 (Senior Pedagogical Evaluator & Cognitive Diagnostic Grader). "
        "Distinguish authentic causal understanding from surface keyword recitation with precision."
    )

    try:
        batch_result: LLMBatchEvaluationResult = client.generate_structured(
            prompt=prompt,
            schema=LLMBatchEvaluationResult,
            tier="reasoning",
            system_instruction=system_instruction,
            temperature=0.1,
        )
    except Exception as e:
        logger.error("LLM evaluation failed (%s). Using heuristic grading fallback.", e)
        # Fallback grading
        fallback_evals = []
        for ans in answers:
            word_count = len(ans.answer_text.split())
            score = min(0.85, max(0.25, word_count / 30.0))
            fallback_evals.append(
                LLMAnswerEvaluation(
                    factual_accuracy=score,
                    causal_depth=max(0.2, score - 0.1),
                    feedback="Preliminary response recorded. Continue to the workspace for guided practice.",
                    identified_misconception=None,
                )
            )
        batch_result = LLMBatchEvaluationResult(
            evaluations=fallback_evals,
            overall_summary="Initial diagnostic baseline captured. Entering adaptive curriculum.",
        )

    # Process evaluation results and update ConceptNodeState ratings
    eval_items: List[DiagnosticEvaluationItem] = []
    total_rating = 0.0
    detected_misconceptions = list(session.detected_misconceptions)

    for i, ans in enumerate(answers):
        res = (
            batch_result.evaluations[i]
            if i < len(batch_result.evaluations)
            else LLMAnswerEvaluation(
                factual_accuracy=0.3,
                causal_depth=0.2,
                feedback="Response evaluated.",
            )
        )
        # Fused rating formula: 60% factual accuracy + 40% causal depth
        node_rating = round((0.6 * res.factual_accuracy) + (0.4 * res.causal_depth), 2)
        total_rating += node_rating

        if res.identified_misconception and res.identified_misconception not in detected_misconceptions:
            detected_misconceptions.append(res.identified_misconception)

        eval_items.append(
            DiagnosticEvaluationItem(
                question_id=ans.question_id,
                concept_id=ans.concept_id,
                factual_accuracy=res.factual_accuracy,
                causal_depth=res.causal_depth,
                feedback=res.feedback,
                identified_misconception=res.identified_misconception,
            )
        )

        # Update node in concept_graph
        node = concept_map.get(ans.concept_id)
        if node:
            node.mastery_rating = node_rating
            node.attempts = 1
            if node_rating >= 0.75:
                node.status = "MASTERED"
            else:
                node.status = "ACTIVE"

    overall_initial_rating = round(total_rating / max(1, len(answers)), 2)

    # Determine next active concept via topological graph progression
    next_active_id = get_next_unlocked_concept(session.concept_graph)
    if not next_active_id and session.concept_graph:
        next_active_id = session.concept_graph[0].concept_id

    # Update concept_graph node statuses according to prerequisite fulfillment
    for node in session.concept_graph:
        if node.concept_id == next_active_id and node.status != "MASTERED":
            node.status = "ACTIVE"

    updated_session = session.model_copy(
        update={
            "concept_graph": session.concept_graph,
            "active_concept_id": next_active_id,
            "detected_misconceptions": detected_misconceptions,
            "last_technique_used": "BASELINE_DIAGNOSTIC_EVALUATION",
        }
    )

    # Execute LangGraph state machine to select the appropriate pedagogical tier payload
    final_session, action_payload = execute_turn(updated_session)

    return DiagnosticEvaluationResponse(
        session=final_session,
        evaluations=eval_items,
        action=action_payload,
        overall_initial_rating=overall_initial_rating,
        summary=batch_result.overall_summary,
    )
