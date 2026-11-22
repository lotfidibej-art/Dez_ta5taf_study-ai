import logging
from typing import List, Optional, Union
from pydantic import BaseModel, Field

from app.orchestrator.graph_utils import get_one_hop_slice
from app.schemas.contracts import (
    MisconceptionTrapPayload,
    ProtegeStagePayload,
    SessionState,
)
from app.services.llm_client import GeminiLLMClient, get_llm_client

logger = logging.getLogger(__name__)


# ==============================================================================
# Structured Output Schemas for Agent 7
# ==============================================================================

class StructuredMisconceptionTrap(BaseModel):
    scenario_intro: str = Field(
        ...,
        description="Plausible context, such as a peer proposing an implementation or proof that fails an edge case.",
    )
    flawed_artifact: str = Field(
        ...,
        description="The code, mathematical equation, or analytical text containing exactly ONE realistic conceptual error.",
    )
    artifact_language: str = Field(
        default="python",
        description="Language or format: 'python', 'mathematics', 'sql', or 'markdown'.",
    )
    hidden_flaw_tag: str = Field(
        ...,
        description="Precise technical tag describing the conceptual fallacy (e.g. 'OFF_BY_ONE_UPPER_BOUND', 'CONFLATING_CORRELATION_WITH_CAUSATION').",
    )


class StructuredProtegeQuestion(BaseModel):
    ai_persona_question: str = Field(
        ...,
        description="Curious, slightly confused peer question asking WHY a specific edge case behaves unexpectedly.",
    )
    target_explanation_points: List[str] = Field(
        ...,
        min_length=2,
        max_length=4,
        description="2 to 3 essential causal explanation criteria the student must state to resolve the peer's confusion.",
    )


def generate_mastery_challenge(
    session_state: SessionState,
    llm: Optional[GeminiLLMClient] = None,
) -> Union[MisconceptionTrapPayload, ProtegeStagePayload]:
    """Agent 7: Adversarial Mastery & Protégé Challenge Generator (> 0.75 mastery tier).

    Inspects session_state.domain_strategy_weights:
    - If socratic / protege weight > misconception weight -> Emits PROTEGE_VOICE_STAGE.
    - Otherwise -> Emits MISCONCEPTION_TRAP.
    """
    client = llm or get_llm_client()

    slice_data = get_one_hop_slice(session_state)
    active_concept = slice_data.get("active_concept", {})
    active_title = active_concept.get("title", session_state.topic_title)
    summary_hook = active_concept.get("summary_hook", "")
    domain = session_state.domain
    weights = session_state.domain_strategy_weights

    # Dynamic Strategy Selection: check weights or alternate
    protege_weight = weights.get("protege", weights.get("socratic", 1.0))
    trap_weight = weights.get("misconception_traps", weights.get("adversarial", 1.0))

    # Alternate or choose based on weights
    use_protege = protege_weight > trap_weight or (
        session_state.last_technique_used == "MISCONCEPTION_TRAP"
    )

    if use_protege:
        return _generate_protege_challenge(
            client=client,
            session_state=session_state,
            active_title=active_title,
            summary_hook=summary_hook,
            domain=domain,
        )
    else:
        return _generate_misconception_trap(
            client=client,
            session_state=session_state,
            active_title=active_title,
            summary_hook=summary_hook,
            domain=domain,
        )


def _generate_misconception_trap(
    client: GeminiLLMClient,
    session_state: SessionState,
    active_title: str,
    summary_hook: str,
    domain: str,
) -> MisconceptionTrapPayload:
    """Mode A: Crafts a subtle, deceptive bug or logical fallacy."""
    system_instruction = (
        "You are Agent 7 (Adversarial Mastery Architect). "
        "The student has established foundational and scaffolding mastery (> 0.75). "
        "Construct an adversarial MISCONCEPTION TRAP. Present a plausible implementation, proof, or scenario "
        "that looks 95% correct on standard happy paths, but contains ONE subtle, catastrophic conceptual fallacy "
        "or boundary violation. The student's task is to pinpoint and explain this hidden trap."
    )

    prompt = (
        f"Domain: {domain}\n"
        f"Topic: {session_state.topic_title}\n"
        f"Active Concept: {active_title}\n"
        f"Core Mechanism: {summary_hook}\n"
        f"Detected Past Misconceptions: {session_state.detected_misconceptions}\n\n"
        "Design a high-fidelity trap scenario:\n"
        "1. scenario_intro: Frame a believable peer's solution.\n"
        "2. flawed_artifact: The code, proof, or passage containing the intentional flaw.\n"
        "3. artifact_language: 'python', 'mathematics', or 'markdown'.\n"
        "4. hidden_flaw_tag: Technical tag summarizing the exact error for automated grading."
    )

    try:
        trap: StructuredMisconceptionTrap = client.generate_structured(
            prompt=prompt,
            schema=StructuredMisconceptionTrap,
            tier="reasoning",
            system_instruction=system_instruction,
            temperature=0.2,
        )

        return MisconceptionTrapPayload(
            ui_component="MISCONCEPTION_TRAP",
            concept_id=session_state.active_concept_id,
            scenario_intro=trap.scenario_intro,
            flawed_artifact=trap.flawed_artifact,
            artifact_language=trap.artifact_language,
            hidden_flaw_tag=trap.hidden_flaw_tag,
        )

    except Exception as e:
        logger.error("Agent 7 Misconception generation failed (%s). Emitting fallback trap.", e)
        return MisconceptionTrapPayload(
            ui_component="MISCONCEPTION_TRAP",
            concept_id=session_state.active_concept_id,
            scenario_intro=(
                f"A colleague claims their implementation of '{active_title}' passes all unit tests "
                "and is ready for deployment. Inspect their logic and identify the critical edge-case vulnerability."
            ),
            flawed_artifact=(
                f"# Implementation for {active_title}\n"
                "def execute_concept(data_stream):\n"
                "    results = []\n"
                "    for idx in range(len(data_stream)):\n"
                "        # Assumes stream values are always strictly positive\n"
                "        val = data_stream[idx]\n"
                "        normalized = val / data_stream[idx - 1]  # Potential zero or boundary wrap bug\n"
                "        results.append(normalized)\n"
                "    return results"
            ),
            artifact_language="python",
            hidden_flaw_tag="NEGATIVE_INDEX_WRAPAROUND_AND_DIVISION_BY_ZERO",
        )


def _generate_protege_challenge(
    client: GeminiLLMClient,
    session_state: SessionState,
    active_title: str,
    summary_hook: str,
    domain: str,
) -> ProtegeStagePayload:
    """Mode B: Crafts a Protégé teaching scenario (peer asking for causal explanation)."""
    turn_num = session_state.protege_turn_count + 1
    is_follow_up = session_state.protege_turn_count > 0

    system_instruction = (
        "You are Agent 7 acting in Protégé Mode (The Protégé Effect / Learning by Teaching). "
        "Adopt the persona of an inquisitive, sincere peer learner who understands the basic formulas "
        "but gets thoroughly confused when faced with an edge-case or non-intuitive consequence. "
        "Pose a targeted question asking WHY something occurs, along with 2-3 essential explanation points "
        "the student must cover to clarify your doubt."
    )

    if is_follow_up:
        prompt = (
            f"Domain: {domain}\n"
            f"Topic: {session_state.topic_title}\n"
            f"Active Concept: {active_title}\n"
            f"Core Mechanism: {summary_hook}\n\n"
            f"The student just gave an initial explanation, but needs to prove durable mastery (Turn {turn_num}).\n"
            "Generate a follow-up Socratic pushback question from the peer learner:\n"
            "1. ai_persona_question: A thoughtful counter-question like 'Wait, but if that is true, then why doesn't [edge case] happen?' or 'I see, but how does the system distinguish between [X] and [Y]?'\n"
            "2. target_explanation_points: 2 to 3 deeper causal criteria required to settle this edge-case challenge."
        )
    else:
        prompt = (
            f"Domain: {domain}\n"
            f"Topic: {session_state.topic_title}\n"
            f"Active Concept: {active_title}\n"
            f"Core Mechanism: {summary_hook}\n\n"
            "Generate an initial Protégé scenario:\n"
            "1. ai_persona_question: An engaging, authentic question from a struggling study partner.\n"
            "2. target_explanation_points: 2 to 3 criteria required to adequately explain the concept."
        )

    try:
        protege: StructuredProtegeQuestion = client.generate_structured(
            prompt=prompt,
            schema=StructuredProtegeQuestion,
            tier="reasoning",
            system_instruction=system_instruction,
            temperature=0.3,
        )

        return ProtegeStagePayload(
            ui_component="PROTEGE_VOICE_STAGE",
            concept_id=session_state.active_concept_id,
            ai_persona_question=protege.ai_persona_question,
            target_explanation_points=protege.target_explanation_points,
            require_voice_input=True,  # Voice enabled for Slice 5
            follow_up_pushback=protege.ai_persona_question if is_follow_up else None,
            turn_number=turn_num,
        )

    except Exception as e:
        logger.error("Agent 7 Protégé generation failed (%s). Emitting fallback.", e)
        fallback_q = (
            f"Wait, but if {active_title} operates that way, what stops a boundary collision or race condition under load? How does the mechanism prevent failure?"
            if is_follow_up
            else f"I get the basic formula for {active_title}, but why does it behave completely differently when extreme values or edge constraints are introduced? Can you walk me through the mechanics?"
        )
        return ProtegeStagePayload(
            ui_component="PROTEGE_VOICE_STAGE",
            concept_id=session_state.active_concept_id,
            ai_persona_question=fallback_q,
            target_explanation_points=[
                f"Clarify the boundary condition where {active_title} shifts state.",
                "Explain the causal mechanism governing why this difference occurs.",
            ],
            require_voice_input=True,
            follow_up_pushback=fallback_q if is_follow_up else None,
            turn_number=turn_num,
        )
