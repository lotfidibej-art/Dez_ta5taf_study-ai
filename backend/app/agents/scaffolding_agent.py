import logging
import re
from typing import Any, Dict, List, Optional
import numpy as np
from pydantic import BaseModel, Field

from app.db.migrations import get_db_connection
from app.orchestrator.graph_utils import get_one_hop_slice
from app.schemas.contracts import (
    ContingentHint,
    FadedWorkspacePayload,
    SessionState,
    SourceCitation,
)
from app.services.llm_client import GeminiLLMClient, get_llm_client
from app.services.local_models import LocalMLService

logger = logging.getLogger(__name__)


# ==============================================================================
# Structured Output Schema for Agent 6 Problem Generator
# ==============================================================================

class StepItem(BaseModel):
    step_number: int = Field(..., ge=1, le=5)
    is_faded: bool = Field(..., description="False for worked demonstrations; True for student blanks.")
    label: str = Field(..., description="Short title like 'Define Base Condition' or 'Apply Identity'.")
    worked_code_or_text: Optional[str] = Field(
        None,
        description="For worked steps (is_faded=False), the full code or worked mathematical derivation.",
    )
    faded_prompt_or_code: Optional[str] = Field(
        None,
        description="For faded steps (is_faded=True), the code or equation with blanks like 'return n + _______' or 'd/dx = _______'.",
    )
    annotation: str = Field(..., description="Pedagogical rationale explaining this step.")
    expected_concept_check: Optional[str] = Field(
        None,
        description="Hidden concept check rubric used by Agent 3 to grade the student's blank completion.",
    )
    expected_token: Optional[str] = Field(
        None,
        description="Concise reference token or value expected in the blank.",
    )


class StructuredFadedProblem(BaseModel):
    problem_statement: str = Field(
        ...,
        description="Realistic, domain-calibrated challenge prompt requiring decomposition.",
    )
    steps: List[StepItem] = Field(
        ...,
        min_length=4,
        max_length=5,
        description="4 to 5 steps where steps 1-2 are worked and steps 3-5 are progressively faded.",
    )
    level_1_conceptual_nudge: str = Field(
        ...,
        description="1-sentence Socratic question pointing toward the core rule without revealing the answer.",
    )
    level_3_skeleton_template: str = Field(
        ...,
        description="Structural template or formula skeleton guiding step execution.",
    )


def generate_faded_workspace(
    session_state: SessionState,
    llm: Optional[GeminiLLMClient] = None,
) -> FadedWorkspacePayload:
    """Agent 6 (Scaffolding & Faded Example Architect).

    Generates a 4-to-5 step worked problem:
    - Steps 1-2: Fully worked demonstration (is_faded=False).
    - Steps 3-5: Partially masked / faded steps (is_faded=True) with expected_concept_check.
    - Resets current_hint_level to 0.
    """
    client = llm or get_llm_client()
    session_state.current_hint_level = 0

    # 1. Deterministic 1-hop context slicer
    slice_data = get_one_hop_slice(session_state)
    active_concept = slice_data.get("active_concept", {})
    immediate_prereqs = slice_data.get("immediate_prerequisites", [])
    misconceptions = session_state.detected_misconceptions

    active_title = active_concept.get("title", session_state.topic_title)
    summary_hook = active_concept.get("summary_hook", "")
    domain = session_state.domain

    system_instruction = (
        "You are Agent 6 (Cognitive Scaffolding & Faded Example Engineer). "
        "Your role is to guide students through the 0.40 - 0.75 mastery tier using Atkinson & Renkl's "
        "Faded Example paradigm. Provide 4 to 5 sequential steps to solve a concrete problem. "
        "Steps 1 and 2 MUST be complete worked demonstrations (is_faded=False). "
        "Steps 3, 4, and (optionally) 5 MUST be faded (is_faded=True), giving a partial prompt or template "
        "with blanks ('_______') for the student to solve, along with an expected_concept_check rubric."
    )

    domain_guidance = {
        "computer_science": "Provide a runnable code trace or algorithm implementation with functions and recurrence/loops.",
        "mathematics": "Provide a rigorous step-by-step algebraic derivation, theorem application, or calculus operation.",
        "physics": "Provide a free-body / equation-of-motion decomposition connecting conservation laws to kinematic formulas.",
        "biology": "Provide a biochemical or physiological step-by-step pathway cascade.",
    }.get(domain.lower(), "Provide a structured logical progression with clear premise and consequence steps.")

    prompt = (
        f"Domain: {domain}\n"
        f"Topic: {session_state.topic_title}\n"
        f"Active Concept: {active_title}\n"
        f"Concept Hook: {summary_hook}\n"
        f"Prerequisites: {[p.get('title') for p in immediate_prereqs]}\n"
        f"Known Student Misconceptions: {misconceptions}\n\n"
        f"Domain Guidance: {domain_guidance}\n\n"
        "Construct a high-quality Faded Problem with:\n"
        "1. problem_statement: Clear real-world or computational objective.\n"
        "2. steps: 4 to 5 steps. Steps 1-2 worked, steps 3+ faded with blanks and expected_concept_check.\n"
        "3. level_1_conceptual_nudge: Socratic 1-sentence hint for the first faded step.\n"
        "4. level_3_skeleton_template: Syntactic / algebraic skeleton template for the first faded step."
    )

    try:
        problem: StructuredFadedProblem = client.generate_structured(
            prompt=prompt,
            schema=StructuredFadedProblem,
            tier="reasoning",
            system_instruction=system_instruction,
            temperature=0.2,
        )

        formatted_steps = []
        for s in problem.steps:
            step_dict: Dict[str, Any] = {
                "step_number": s.step_number,
                "step_type": "FADED" if s.is_faded else "WORKED",
                "is_faded": s.is_faded,
                "label": s.label,
                "code": s.worked_code_or_text if not s.is_faded else s.faded_prompt_or_code,
                "annotation": s.annotation,
                "expected_concept_check": s.expected_concept_check,
                "expected_token": s.expected_token,
                "blank_id": f"faded_step_{s.step_number}" if s.is_faded else None,
            }
            formatted_steps.append(step_dict)

        return FadedWorkspacePayload(
            ui_component="FADED_EXAMPLE_WORKSPACE",
            concept_id=session_state.active_concept_id,
            problem_statement=problem.problem_statement,
            steps=formatted_steps,
            active_hint=None,
        )

    except Exception as e:
        logger.error("Agent 6 LLM generation failed (%s). Emitting robust domain fallback.", e)
        return _fallback_faded_workspace(session_state, active_title)


def _fallback_faded_workspace(session_state: SessionState, active_title: str) -> FadedWorkspacePayload:
    """Pedagogically sound fallback for Faded Workspace."""
    return FadedWorkspacePayload(
        ui_component="FADED_EXAMPLE_WORKSPACE",
        concept_id=session_state.active_concept_id,
        problem_statement=f"Implement and verify the step-by-step transition for '{active_title}'.",
        steps=[
            {
                "step_number": 1,
                "step_type": "WORKED",
                "is_faded": False,
                "label": "Establish Boundary / Preconditions",
                "code": "# Validate inputs and set foundational constraints\nif input_val is None:\n    return default_state",
                "annotation": "Guarantees valid execution state before entering the core processing loop.",
            },
            {
                "step_number": 2,
                "step_type": "WORKED",
                "is_faded": False,
                "label": "Decompose Primary Transition",
                "code": "# Primary causal transformation step\nintermediate = compute_primary_transform(input_val)",
                "annotation": "Applies the governing rule to calculate the intermediate state.",
            },
            {
                "step_number": 3,
                "step_type": "FADED",
                "is_faded": True,
                "label": "Complete State Accumulation",
                "code": "result = intermediate + _______",
                "annotation": "Combine the intermediate transformation with the accumulated remainder.",
                "expected_concept_check": "Combines transformed subproblem with base accumulator.",
                "expected_token": "accumulated_state",
                "blank_id": "faded_step_3",
            },
            {
                "step_number": 4,
                "step_type": "FADED",
                "is_faded": True,
                "label": "Return Final Converged Output",
                "code": "return _______",
                "annotation": "Ensure returned output conforms to system contracts.",
                "expected_concept_check": "Returns result satisfying invariant.",
                "expected_token": "result",
                "blank_id": "faded_step_4",
            },
        ],
        active_hint=None,
    )


# ==============================================================================
# Contingent Hint Ladder Generator (Level 1, Level 2, Level 3)
# ==============================================================================

def generate_contingent_hint(
    session_state: SessionState,
    current_workspace: FadedWorkspacePayload,
    db_conn=None,
    llm: Optional[GeminiLLMClient] = None,
) -> ContingentHint:
    """Generates the next progressive hint in the Contingent Hint Ladder (Levels 1 to 3).

    - Level 1 (Conceptual Nudge): Socratic question targeting the principle without giving answers.
    - Level 2 (Source Pointer): STRICT GROUNDING. Queries PostgreSQL resource_chunks for active_concept_id
      and quotes exact source citations (file_name + page/timestamp).
    - Level 3 (Structural Skeleton): Code / formula template with blanks.
    """
    client = llm or get_llm_client()
    target_level = min(session_state.current_hint_level + 1, 3)

    # Locate first faded step
    faded_steps = [s for s in current_workspace.steps if s.get("is_faded") or s.get("step_type") == "FADED"]
    first_faded = faded_steps[0] if faded_steps else (current_workspace.steps[-1] if current_workspace.steps else {})
    step_label = first_faded.get("label", "the faded step")
    concept_check = first_faded.get("expected_concept_check", "")
    code_snippet = first_faded.get("code", "")

    active_concept_id = session_state.active_concept_id

    # --------------------------------------------------------------------------
    # Level 1: Conceptual Socratic Nudge
    # --------------------------------------------------------------------------
    if target_level == 1:
        prompt = (
            f"Topic: {session_state.topic_title}\n"
            f"Active Concept: {active_concept_id}\n"
            f"Step: {step_label}\n"
            f"Expected Concept: {concept_check}\n\n"
            "Write exactly ONE gentle Socratic question (under 25 words) guiding the student's attention "
            "to the underlying invariant or rule needed here without revealing any solution syntax."
        )
        try:
            from pydantic import BaseModel, Field

            class Level1Response(BaseModel):
                nudge_text: str = Field(..., max_length=150)

            res: Level1Response = client.generate_structured(
                prompt=prompt,
                schema=Level1Response,
                tier="fast",
                temperature=0.3,
            )
            hint_text = res.nudge_text.strip()
        except Exception:
            hint_text = f"Consider how the invariant in '{step_label}' must preserve equilibrium or boundary conditions."

        return ContingentHint(
            level=1,
            hint_type="CONCEPTUAL_NUDGE",
            hint_text=hint_text,
            source_citation=None,
            skeleton_template=None,
        )

    # --------------------------------------------------------------------------
    # Level 2: Strict Source Pointer with PostgreSQL Resource Chunks Citation
    # --------------------------------------------------------------------------
    elif target_level == 2:
        citation: Optional[SourceCitation] = None
        source_snippet = ""

        # Fetch closest resource chunk from PostgreSQL
        try:
            conn_context = db_conn if db_conn else get_db_connection()
            with conn_context as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT source_name, source_location, content 
                        FROM resource_chunks 
                        WHERE session_id = %s AND (concept_id = %s OR concept_id IS NOT NULL)
                        ORDER BY (concept_id = %s) DESC, chunk_id ASC 
                        LIMIT 1
                        """,
                        (session_state.session_id, active_concept_id, active_concept_id),
                    )
                    row = cur.fetchone()
                    if row:
                        source_name, source_location, content = row
                        citation = SourceCitation(
                            file_name=source_name,
                            page_or_timestamp=source_location,
                        )
                        source_snippet = content[:250].strip()
        except Exception as e:
            logger.warning("Could not query resource_chunks for Level 2 hint citation: %s", e)

        if not citation:
            # Fallback citation if no file chunks uploaded
            citation = SourceCitation(
                file_name="Curriculum Syllabus",
                page_or_timestamp="Core Module Definition",
            )
            hint_text = f"Review the foundational definition in your syllabus: pay special attention to the transition rule for {step_label}."
        else:
            hint_text = (
                f"Refer to {citation.file_name} ({citation.page_or_timestamp}). "
                f"The text notes: \"{source_snippet}...\" — apply this principle directly to {step_label}."
            )

        return ContingentHint(
            level=2,
            hint_type="SOURCE_POINTER",
            hint_text=hint_text,
            source_citation=citation,
            skeleton_template=None,
        )

    # --------------------------------------------------------------------------
    # Level 3: Structural Skeleton / Formula Frame
    # --------------------------------------------------------------------------
    else:
        prompt = (
            f"Step: {step_label}\n"
            f"Current Prompt: {code_snippet}\n"
            f"Expected Concept: {concept_check}\n\n"
            "Provide a structural template / formula skeleton (e.g. 'return current_val + [recurse(next_state)]' "
            "or 'F_net = m * (dv/dt)') that exposes the complete syntactic pattern while leaving the final parameters blank."
        )
        skeleton = code_snippet
        try:
            from pydantic import BaseModel, Field

            class Level3Response(BaseModel):
                skeleton_template: str = Field(...)
                explanation_tip: str = Field(...)

            res3: Level3Response = client.generate_structured(
                prompt=prompt,
                schema=Level3Response,
                tier="fast",
                temperature=0.2,
            )
            skeleton = res3.skeleton_template.strip()
            hint_text = res3.explanation_tip.strip()
        except Exception:
            hint_text = f"Fill in the missing parameter into the required skeleton: {skeleton}"

        return ContingentHint(
            level=3,
            hint_type="STRUCTURAL_SKELETON",
            hint_text=hint_text,
            source_citation=None,
            skeleton_template=skeleton,
        )
