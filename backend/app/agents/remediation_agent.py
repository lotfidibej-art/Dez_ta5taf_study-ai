import json
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.db.migrations import get_db_connection
from app.orchestrator.graph_utils import get_one_hop_slice
from app.schemas.contracts import (
    AutoHint,
    CounterExample,
    FadedWorkspacePayload,
    RemediationFeedback,
    SessionState,
    SourceCitation,
)
from app.services.llm_client import GeminiLLMClient, get_llm_client
from app.agents.scaffolding_agent import generate_contingent_hint

logger = logging.getLogger(__name__)


# ==============================================================================
# Structured Output Schema for Gemini 3.8 Flash Remediation Agent
# ==============================================================================

class StructuredCounterExample(BaseModel):
    diagnosis_summary: str = Field(
        ...,
        description="1-2 sentences explaining precisely what went wrong in the student's reasoning.",
    )
    title: str = Field(
        default="Counter-Example: When Your Rule Breaks",
        description="Engaging title like 'Counter-Example: When Broadcast Overrides Local Routing'.",
    )
    input_or_scenario: str = Field(
        ...,
        description="Concrete edge-case input, code execution trace, or mathematical/domain counter-scenario.",
    )
    expected_vs_student_outcome: str = Field(
        ...,
        description="Clear comparison showing what the student's rule predicts vs. what actually happens.",
    )


def build_mistake_remediation(
    session_state: SessionState,
    student_submission: str,
    identified_misconception: Optional[str] = None,
    evaluation_feedback: Optional[str] = None,
    active_action: Optional[Any] = None,
    db_conn=None,
    llm: Optional[GeminiLLMClient] = None,
) -> RemediationFeedback:
    """Agent: Mistake Remediation Engine.

    When a student submits a wrong, incomplete, or surface-memorized answer:
    1. Increments consecutive_mistakes.
    2. Uses Gemini (reasoning tier) to construct the simplest possible Counter-Example
       that breaks the student's specific assumption without giving away the answer.
    3. Automatically escalates the Contingent Hint Ladder (+1 tier), fetching real
       resource_chunks citations if reaching Level 2.
    4. Evaluates whether to trigger should_backtrack_prerequisite if consecutive_mistakes >= 3.
    """
    client = llm or get_llm_client()
    consecutive_mistakes = session_state.consecutive_mistakes + 1

    # 1. Inspect 1-hop slice & resource chunks
    slice_data = get_one_hop_slice(session_state)
    active_concept = slice_data.get("active_concept", {})
    concept_title = active_concept.get("title", session_state.topic_title)
    summary_hook = active_concept.get("summary_hook", "")

    # Fetch ground-truth snippets from resource_chunks for context
    resource_snippets: List[str] = []
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT content, source_name, source_location
                    FROM resource_chunks
                    WHERE session_id = %s AND concept_id = %s
                    LIMIT 3
                    """,
                    (session_state.session_id, session_state.active_concept_id),
                )
                for row in cur.fetchall():
                    resource_snippets.append(f"[{row[1]} - {row[2]}]:\n{row[0]}")
    except Exception as e:
        logger.warning("Could not query resource chunks for remediation: %s", e)

    context_str = "\n\n".join(resource_snippets)[:3000] if resource_snippets else summary_hook

    system_instruction = (
        "You are the Mistake Remediation Agent in an Adaptive AI Learning Platform. "
        "The student has submitted an incorrect, incomplete, or flawed response. "
        "Your task is to generate a concrete Counter-Example that directly exposes the flaw in the student's assumption. "
        "Rule 1: Never give away the full final solution or correct formula directly. "
        "Rule 2: Make the counter-example concrete (specific test input, boundary case, or scenario) "
        "showing why their assumption produces an invalid or contradictory result."
    )

    prompt = (
        f"Domain: {session_state.domain}\n"
        f"Active Concept: {concept_title} ({session_state.active_concept_id})\n"
        f"Core Principle: {summary_hook}\n"
        f"Reference Content:\n{context_str}\n\n"
        f"Student Submission:\n\"{student_submission}\"\n"
        f"Identified Flaw / Misconception: {identified_misconception or evaluation_feedback or 'Incorrect conceptual application'}\n\n"
        "Construct the simplest possible counter-example breaking this specific flawed assumption."
    )

    try:
        structured_ce: StructuredCounterExample = client.generate_structured(
            prompt=prompt,
            schema=StructuredCounterExample,
            tier="reasoning",
            system_instruction=system_instruction,
            temperature=0.2,
        )
        diag_summary = structured_ce.diagnosis_summary
        ce_title = structured_ce.title
        ce_input = structured_ce.input_or_scenario
        ce_outcome = structured_ce.expected_vs_student_outcome
    except Exception as e:
        logger.warning("Remediation LLM generation failed (%s). Emitting robust domain fallback.", e)
        diag_summary = (
            f"Your response overlooks the core invariant governing '{concept_title}'. "
            "The assumed rule fails when tested against non-standard boundary conditions."
        )
        ce_title = f"Counter-Example: Edge Condition for {concept_title}"
        ce_input = f"Consider an edge input where constraints are constrained to minimum or maximum boundaries in {concept_title}."
        ce_outcome = "Your rule predicts a standard linear progression, but the system actually triggers a boundary exception or wraparound."

    counter_example_obj = CounterExample(
        title=ce_title,
        input_or_scenario=ce_input,
        expected_vs_student_outcome=ce_outcome,
    )

    # 2. Escalate Contingent Hint Ladder (+1 level)
    # Prepare workspace payload for contingent hint generator
    workspace_for_hint = active_action
    if not isinstance(workspace_for_hint, FadedWorkspacePayload):
        workspace_for_hint = FadedWorkspacePayload(
            ui_component="FADED_EXAMPLE_WORKSPACE",
            concept_id=session_state.active_concept_id,
            problem_statement=f"Mastery practice on {concept_title}",
            steps=[],
            active_hint=None,
        )

    contingent_hint = generate_contingent_hint(
        session_state=session_state,
        current_workspace=workspace_for_hint,
        db_conn=db_conn,
        llm=client,
    )

    auto_hint_obj = AutoHint(
        level=min(contingent_hint.level, 3),  # type: ignore
        hint_text=contingent_hint.hint_text,
        source_citation=contingent_hint.source_citation,
    )

    # 3. Check Prerequisite Backtracking condition
    # Trigger if consecutive_mistakes >= 3 and active concept has unmastered parent prerequisites
    should_backtrack = False
    active_node = next(
        (n for n in session_state.concept_graph if n.concept_id == session_state.active_concept_id),
        None,
    )
    if consecutive_mistakes >= 3 and active_node and active_node.prerequisites:
        # Check if any parent prerequisite is unmastered (< 0.85)
        for prereq_id in active_node.prerequisites:
            prereq_node = next((n for n in session_state.concept_graph if n.concept_id == prereq_id), None)
            if prereq_node and prereq_node.mastery_rating < 0.85:
                should_backtrack = True
                break

    return RemediationFeedback(
        is_mistake=True,
        consecutive_mistakes=consecutive_mistakes,
        diagnosis_summary=diag_summary,
        counter_example=counter_example_obj,
        auto_hint=auto_hint_obj,
        should_backtrack_prerequisite=should_backtrack,
    )
