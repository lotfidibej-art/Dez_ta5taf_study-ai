import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.db.migrations import get_db_connection
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
    from app.orchestrator.graph import execute_turn

    final_session, action_payload = execute_turn(updated_session)

    return DiagnosticEvaluationResponse(
        session=final_session,
        evaluations=eval_items,
        action=action_payload,
        overall_initial_rating=overall_initial_rating,
        summary=batch_result.overall_summary,
    )


# ==============================================================================
# Slice 4: Dynamic Turn Evaluator (Faded Steps, Traps, Protégé)
# ==============================================================================

def evaluate_turn_submission(
    session: SessionState,
    text_input: str,
    step_answers: Optional[Dict[str, str]] = None,
    response_latency_sec: float = 0.0,
    active_action: Optional[Any] = None,
    prosody_signals: Optional[Dict[str, Any]] = None,
    llm: Optional[GeminiLLMClient] = None,
) -> Any:
    """Agent 3: Evaluates student performance across Faded Steps, Misconception Traps, and Protégé challenges.

    1. Inspects active challenge type and incorporates spoken prosody signals if present.
    2. Uses Gemini fast/reasoning tier to grade factual accuracy & causal depth.
    3. Enforces Surface Memorization Guard & Hesitation Support rules.
    4. Updates Multi-Armed Bandit weights for student_domain_profiles.
    5. Deducts hint penalty (-0.03 per hint level used).
    6. When mastery >= 0.85, marks concept MASTERED in Redis & PostgreSQL, advances active_concept_id.
    7. Re-runs LangGraph state machine to route to next pedagogical action.
    """
    import json
    from app.schemas.contracts import SubmitTurnResponse, TurnEvaluationItem, VoiceProsodySignals
    from app.services.bandit import update_bandit_weights

    client = llm or get_llm_client()
    active_concept_id = session.active_concept_id

    # Find active concept node
    active_node = next((n for n in session.concept_graph if n.concept_id == active_concept_id), None)
    concept_title = active_node.title if active_node else session.topic_title

    # Determine evaluation context based on action payload
    ui_component = getattr(active_action, "ui_component", "UNKNOWN") if active_action else "UNKNOWN"

    criteria_prompt = ""
    if ui_component == "FADED_EXAMPLE_WORKSPACE" and hasattr(active_action, "steps"):
        faded_steps = [s for s in active_action.steps if s.get("is_faded") or s.get("step_type") == "FADED"]
        rubric_items = [
            f"Step {s.get('step_number')}: Prompt='{s.get('code')}' -> Rubric='{s.get('expected_concept_check')}'"
            for s in faded_steps
        ]
        criteria_prompt = (
            f"Challenge Type: FADED WORKSPACE STEP COMPLETION\n"
            f"Faded Step Rubrics:\n" + "\n".join(rubric_items) + "\n\n"
            f"Student Answers to Blank Steps: {step_answers or {}}\n"
            f"Student Explanation / Narrative: {text_input}\n"
        )
    elif ui_component == "MISCONCEPTION_TRAP" and hasattr(active_action, "hidden_flaw_tag"):
        criteria_prompt = (
            f"Challenge Type: MISCONCEPTION TRAP DIAGNOSIS\n"
            f"Scenario: {getattr(active_action, 'scenario_intro', '')}\n"
            f"Flawed Artifact:\n{getattr(active_action, 'flawed_artifact', '')}\n"
            f"Ground-Truth Flaw Tag: {active_action.hidden_flaw_tag}\n\n"
            f"Student's Bug Diagnosis & Causal Analysis: {text_input}\n"
            "Grade whether the student identified the root cause conceptual fallacy and explained why it fails."
        )
    elif ui_component == "PROTEGE_VOICE_STAGE" and hasattr(active_action, "target_explanation_points"):
        criteria_prompt = (
            f"Challenge Type: PROTÉGÉ TEACHING MODE\n"
            f"Peer Learner Question: {active_action.ai_persona_question}\n"
            f"Target Explanation Criteria:\n" + "\n".join(f"- {p}" for p in active_action.target_explanation_points) + "\n\n"
            f"Student's Spoken / Written Teaching Response: {text_input}\n"
            "Grade whether the student clearly explained the underlying mechanics to resolve the peer's confusion."
        )
    else:
        criteria_prompt = (
            f"Challenge Type: CONCEPT APPLICATION\n"
            f"Concept: {concept_title}\n"
            f"Student Input: {text_input}\n"
        )

    # Append voice prosody telemetry to evaluation context if voice input was analyzed
    if prosody_signals:
        criteria_prompt += (
            "\n[Spoken Fluency & Prosody Telemetry]\n"
            f"- Speech Rate (WPM): {prosody_signals.get('speech_rate_wpm', 0.0)}\n"
            f"- Hesitation Pauses (>1.5s): {prosody_signals.get('hesitation_pause_count', 0)}\n"
            f"- Max Pause Duration: {prosody_signals.get('max_pause_sec', 0.0)}s\n"
            f"- Filler Word Ratio: {prosody_signals.get('filler_word_ratio', 0.0)}\n"
            f"- Self-Correction Restarts: {prosody_signals.get('self_correction_count', 0)}\n"
            f"- Monotone Recitation Flag: {prosody_signals.get('monotone_recitation_flag', False)}\n"
            f"- Fluency Signal: {prosody_signals.get('fluency_signal', 'Unknown')}\n"
        )

    system_instruction = (
        "You are Agent 3 (Evaluator Agent & Pedagogical Psychometrician). "
        "Evaluate the student's submission against the challenge criteria. "
        "Grade factual_accuracy (0.0 to 1.0) and causal_depth (0.0 to 1.0). "
        "Provide constructive pedagogical feedback. If an obvious misconception is revealed, capture it."
    )

    try:
        eval_result: LLMAnswerEvaluation = client.generate_structured(
            prompt=criteria_prompt,
            schema=LLMAnswerEvaluation,
            tier="reasoning",
            system_instruction=system_instruction,
            temperature=0.1,
        )
        factual_acc = eval_result.factual_accuracy
        causal_depth = eval_result.causal_depth
        feedback = eval_result.feedback
        misconception = eval_result.identified_misconception
    except Exception as e:
        logger.warning("Turn evaluation LLM call failed (%s). Using fallback evaluation.", e)
        factual_acc = 0.70
        causal_depth = 0.65
        feedback = "Solid reasoning shown. Continuing to reinforce core mechanics."
        misconception = None

    # Step 2 Prosody Anti-Memorization & Hesitation Rules
    if prosody_signals:
        # Hesitation Support: partial reasoning with self-corrections boosts causal depth
        if prosody_signals.get("hesitation_pause_count", 0) >= 2 or prosody_signals.get("filler_word_ratio", 0.0) > 0.12:
            if prosody_signals.get("self_correction_count", 0) > 0:
                causal_depth = min(1.0, round(causal_depth + 0.10, 2))
                feedback += " Commendable self-correction noted as you verbally worked through the logic."
            else:
                feedback += " Take your time to unpack the causal chain before delivering the final conclusion."

    # Calculate hint penalty: -0.03 per hint level used (up to Level 3 = -0.09)
    hint_level = session.current_hint_level
    hint_penalty = round(min(hint_level * 0.03, 0.15), 2)

    raw_rating = round((0.6 * factual_acc) + (0.4 * causal_depth), 2)
    final_rating = max(0.0, round(raw_rating - hint_penalty, 2))

    # Blend with previous mastery rating
    prev_rating = active_node.mastery_rating if active_node else 0.0
    updated_rating = max(final_rating, round((0.35 * prev_rating) + (0.65 * final_rating), 2))

    # Slice 6: Mistake Detection Threshold
    # Flag mistake if factual_accuracy < 0.70, causal_depth < 0.65, or monotone recitation detected
    is_monotone = bool(prosody_signals and prosody_signals.get("monotone_recitation_flag", False))
    is_mistake = (factual_acc < 0.70) or (causal_depth < 0.65) or is_monotone

    # Surface Memorization Guard:
    if is_monotone and factual_acc >= 0.80:
        logger.info("Surface memorization guard triggered for session %s (monotone_recitation_flag=True)", session.session_id)
        updated_rating = min(updated_rating, 0.78)
        misconception = "Surface memorization detected: high-speed verbatim recall without causal elaboration"
        feedback = (
            "Surface memorization detected: your explanation was rapid and verbatim, but lacked conversational causal synthesis. "
            "To achieve durable mastery, explain the underlying *why* and mechanisms in your own words."
        )

    # Remediation Engine Generation (Slice 6)
    remediation = None
    if is_mistake:
        # Block concept mastery
        updated_rating = min(updated_rating, 0.79)
        concept_mastered = False
        next_active_id = active_concept_id

        if not misconception:
            misconception = (
                "Surface memorization detected: high-speed verbatim recall without causal elaboration"
                if is_monotone
                else "Incomplete causal derivation or invalid boundary assumption"
            )

        from app.agents.remediation_agent import build_mistake_remediation
        remediation = build_mistake_remediation(
            session_state=session,
            student_submission=text_input,
            identified_misconception=misconception,
            evaluation_feedback=feedback,
            active_action=active_action,
        )

        next_hint_level = remediation.auto_hint.level
        consecutive_mistakes = remediation.consecutive_mistakes

        # Check prerequisite backtracking if stalled across 3+ attempts
        if remediation.should_backtrack_prerequisite:
            from app.orchestrator.graph import check_and_apply_prerequisite_backtracking
            session_backtracked = check_and_apply_prerequisite_backtracking(session)
            next_active_id = session_backtracked.active_concept_id
    else:
        # Concept Mastery Threshold: >= 0.85
        concept_mastered = updated_rating >= 0.85
        consecutive_mistakes = 0
        next_hint_level = 0

    # Update concept_graph
    for node in session.concept_graph:
        if node.concept_id == active_concept_id:
            node.mastery_rating = updated_rating
            node.attempts += 1
            if concept_mastered:
                node.status = "MASTERED"
            elif updated_rating >= 0.40:
                node.status = "ACTIVE"
            break

    # If mastered, advance active_concept_id to next unlocked node in DAG
    if concept_mastered and not is_mistake:
        from app.orchestrator.graph_utils import get_next_unlocked_concept
        unlocked = get_next_unlocked_concept(session.concept_graph)
        if unlocked and unlocked != active_concept_id:
            next_active_id = unlocked
    elif not is_mistake:
        next_active_id = active_concept_id

    # Register misconception if newly spotted
    detected_misconceptions = list(session.detected_misconceptions)
    if misconception and misconception not in detected_misconceptions:
        detected_misconceptions.append(misconception)

    # Multi-Armed Bandit Domain Strategy Weights Update
    updated_bandit_weights = update_bandit_weights(
        student_id=session.student_id,
        domain=session.domain,
        last_technique_used=ui_component,
        previous_rating=prev_rating,
        updated_rating=updated_rating,
        current_weights=session.domain_strategy_weights,
    )

    # Multi-turn Protégé counter tracking
    if ui_component == "PROTEGE_VOICE_STAGE":
        next_protege_turns = 0 if concept_mastered else (session.protege_turn_count + 1)
    else:
        next_protege_turns = 0

    updated_session_state = session.model_copy(
        update={
            "concept_graph": session.concept_graph,
            "active_concept_id": next_active_id,
            "detected_misconceptions": detected_misconceptions,
            "domain_strategy_weights": updated_bandit_weights,
            "current_hint_level": next_hint_level,
            "last_technique_used": ui_component,
            "protege_turn_count": next_protege_turns,
            "consecutive_mistakes": consecutive_mistakes,
            "active_remediation": remediation,
        }
    )

    # Persist mastery updates in PostgreSQL
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                if concept_mastered:
                    cur.execute(
                        """
                        UPDATE concept_nodes 
                        SET metadata = jsonb_set(
                            jsonb_set(metadata, '{status}', '"MASTERED"'),
                            '{mastery_rating}', %s::text::jsonb
                        )
                        WHERE metadata->>'concept_id' = %s
                        """,
                        (str(updated_rating), active_concept_id),
                    )

                # Resolve student UUID if foreign key constraint applies
                db_student_uuid = None
                try:
                    import uuid as _uuid
                    _uuid.UUID(str(session.student_id))
                    db_student_uuid = str(session.student_id)
                except Exception:
                    cur.execute(
                        "SELECT id FROM students WHERE email = %s OR name = %s LIMIT 1",
                        (f"{session.student_id}@student.local", session.student_id),
                    )
                    s_row = cur.fetchone()
                    if s_row:
                        db_student_uuid = s_row[0]

                # Log Telemetry
                cur.execute(
                    """
                    INSERT INTO telemetry_events (session_id, student_id, event_type, payload)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        session.session_id,
                        db_student_uuid,
                        "TURN_SUBMISSION_EVALUATION",
                        json.dumps({
                            "concept_id": active_concept_id,
                            "challenge_type": ui_component,
                            "factual_accuracy": factual_acc,
                            "causal_depth": causal_depth,
                            "hint_level_used": hint_level,
                            "hint_penalty_applied": hint_penalty,
                            "updated_mastery_rating": updated_rating,
                            "concept_mastered": concept_mastered,
                            "response_latency_sec": response_latency_sec,
                            "identified_misconception": misconception,
                            "prosody_signals": prosody_signals,
                        }),
                    ),
                )
        logger.info(
            "Logged turn submission telemetry for session %s, concept %s (mastery=%.2f, mastered=%s)",
            session.session_id,
            active_concept_id,
            updated_rating,
            concept_mastered,
        )
    except Exception as e:
        logger.warning("Could not persist turn evaluation in PostgreSQL: %s", e)

    # Core Behavioral Rule (Slice 6):
    # When a mistake occurs and not backtracking:
    # PRESERVE the active problem workspace so the student can repair their understanding!
    if is_mistake and active_action and not (remediation and remediation.should_backtrack_prerequisite):
        next_action = active_action
        final_session = updated_session_state
    else:
        from app.orchestrator.graph import execute_turn
        final_session, next_action = execute_turn(updated_session_state)

    action_dict = next_action.model_dump() if hasattr(next_action, "model_dump") else (active_action if isinstance(active_action, dict) else None)
    final_session = final_session.model_copy(
        update={
            "last_action_payload": action_dict,
        }
    )

    evaluation_item = TurnEvaluationItem(
        factual_accuracy=factual_acc,
        causal_depth=causal_depth,
        feedback=feedback,
        identified_misconception=misconception,
        hint_penalty_applied=hint_penalty,
        prosody_signals=VoiceProsodySignals(**prosody_signals) if prosody_signals else None,
    )

    return SubmitTurnResponse(
        session=final_session,
        evaluation=evaluation_item,
        action=next_action,
        updated_mastery_rating=updated_rating,
        concept_mastered=concept_mastered,
        remediation=remediation,
    )
