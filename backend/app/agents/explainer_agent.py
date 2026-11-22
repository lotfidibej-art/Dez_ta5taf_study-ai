import json
import logging
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.orchestrator.graph_utils import get_one_hop_slice
from app.schemas.contracts import FoundationBoardPayload, SessionState
from app.services.llm_client import GeminiLLMClient, get_llm_client

logger = logging.getLogger(__name__)


# ==============================================================================
# Structured Output Schema for Agent 4
# ==============================================================================

class StructuredBridgeAnalogy(BaseModel):
    source_concept: str = Field(..., description="Familiar concept from past domain or common experience")
    target_concept: str = Field(..., description="The new target concept being explained")
    mapping: str = Field(..., description="Clear structural mapping showing how the familiar concept explains the new one")


class StructuredFoundationResponse(BaseModel):
    bullet_breakdown: List[str] = Field(
        ...,
        min_length=3,
        max_length=5,
        description="3 to 5 concise, concrete bullet points explaining why the mechanism works (no fluff).",
    )
    raw_mermaid_diagram: str = Field(
        ...,
        description="A causal diagram in Mermaid flowchart syntax showing step-by-step state flow.",
    )
    bridge_analogy: Optional[StructuredBridgeAnalogy] = Field(
        default=None,
        description="Analogical bridge linking a previously mastered concept to this active concept.",
    )
    study_habit_nudge: Optional[str] = Field(
        default=None,
        description="Contextual metacognitive coaching tip tailored to the student's attempts or misconceptions.",
    )


# ==============================================================================
# Mermaid Syntax Guard
# ==============================================================================

def sanitize_mermaid_diagram(raw_chart: str) -> str:
    """Sanitizes raw Mermaid chart output from the LLM.

    1. Strips markdown fences (```mermaid ... ```).
    2. Ensures standard header (flowchart TD or graph TD).
    3. Normalizes and wraps node labels in double quotes (e.g. A["Label Text"])
       to prevent parsing failures on parentheses, braces, colons, or punctuation.
    """
    if not raw_chart:
        return "flowchart TD\n    A[\"Core Concept\"] --> B[\"Mechanism\"]"

    chart = raw_chart.strip()

    # Strip code block fences
    if chart.startswith("```"):
        chart = re.sub(r"^```(?:mermaid)?\s*", "", chart, flags=re.IGNORECASE)
    if chart.endswith("```"):
        chart = re.sub(r"\s*```$", "", chart)
    chart = chart.strip()

    lines = [line.rstrip() for line in chart.splitlines() if line.strip()]
    if not lines:
        return "flowchart TD\n    A[\"Core Concept\"] --> B[\"Mechanism\"]"

    # Ensure header exists
    first_line = lines[0].lower().strip()
    if not (first_line.startswith("flowchart") or first_line.startswith("graph")):
        lines.insert(0, "flowchart TD")

    sanitized_lines = [lines[0]]

    # Node label replacement: handles A["label"], A[label], A("label"), A(label), A(["label"]), A([label])
    # Matches node identifier followed by opening bracket/parenthesis, label content, and closing bracket/parenthesis
    node_pattern = re.compile(r'(\b[a-zA-Z0-9_]+)\s*(?:\[\s*|\(\[\s*|\(\s*)(.+?)(?:\s*\]\]|\s*\]\)?|\s*\)\]|\s*\))(?=\s*(?:-->|---|==>|-.->|\||\n|$))')

    for line in lines[1:]:
        processed_line = line

        def _replace_label(m: re.Match) -> str:
            node_id = m.group(1)
            raw_label = m.group(2).strip()

            # Strip existing bounding quotes if present
            if (raw_label.startswith('"') and raw_label.endswith('"')) or (
                raw_label.startswith("'") and raw_label.endswith("'")
            ):
                raw_label = raw_label[1:-1].strip()

            safe_label = raw_label.replace('"', "'")
            return f'{node_id}["{safe_label}"]'

        processed_line = node_pattern.sub(_replace_label, processed_line)
        sanitized_lines.append(processed_line)

    return "\n".join(sanitized_lines)


# ==============================================================================
# Agent 4 Core Function
# ==============================================================================

def generate_foundation_board(
    session_state: SessionState,
    llm: Optional[GeminiLLMClient] = None,
) -> FoundationBoardPayload:
    """Agent 4: Explainer, Cross-Domain Analogy & Visual Agent.

    Strictly abides by:
    1. Pass ONLY get_one_hop_slice() + domain_strategy_weights + detected_misconceptions.
    2. If session.resource_scope == "STRICT_UPLOAD_ONLY", grounds bullets exclusively in
       retrieved resource_chunks and suppresses external analogical inventions.
    3. If ENRICHED_EXTERNAL, leverages analogy_anchor_from_memory for high-impact bridges.
    4. Mermaid Syntax Guard wraps node labels in double quotes.
    """
    client = llm or get_llm_client()

    # 1. Deterministic 1-hop slice extraction
    slice_data = get_one_hop_slice(session_state)
    active_concept = slice_data.get("active_concept", {})
    immediate_prereqs = slice_data.get("immediate_prerequisites", [])
    next_goal = slice_data.get("next_unlocked_goal")
    analogy_anchor = slice_data.get("analogy_anchor_from_memory")
    scope = session_state.resource_scope

    # Build context representation
    resource_chunks = active_concept.get("resource_chunks", [])
    chunk_snippets = []
    for c in resource_chunks:
        chunk_snippets.append(f"[{c.get('source_name', 'Source')} - {c.get('source_location', '')}]:\n{c.get('content', '')}")
    chunks_text = "\n\n".join(chunk_snippets) if chunk_snippets else "No source excerpts available."

    prereq_summary = ", ".join([f"{p['title']} (mastery={p['mastery_rating']:.2f})" for p in immediate_prereqs]) or "None"
    misconceptions_summary = ", ".join(session_state.detected_misconceptions) or "None detected so far"

    system_instruction = (
        "You are Agent 4 (Senior Pedagogical Explainer & Visual Diagrammer). "
        "Your mission is to construct the 'Foundation Board' for a student currently struggling or "
        "establishing foundational understanding (< 40% mastery). "
        "Explain WHY the underlying mechanism functions rather than just giving a dictionary definition. "
        "Generate a strictly valid Mermaid flowchart depicting the causal step sequence."
    )

    scope_rules = ""
    if scope == "STRICT_UPLOAD_ONLY":
        scope_rules = (
            "STRICT CONSTRAINT: resource_scope is STRICT_UPLOAD_ONLY. "
            "You MUST anchor your explanations strictly in the provided SOURCE RESOURCE EXCERPTS below. "
            "Do NOT reference unverified external examples or invent facts outside the text. "
            "If no analogy anchor is provided from memory, leave bridge_analogy null."
        )
    else:
        scope_rules = (
            "resource_scope is ENRICHED_EXTERNAL. "
            "You may utilize broad pedagogical analogies and domain bridges to crystallize the concept."
        )

    analogy_prompt = ""
    if analogy_anchor and scope == "ENRICHED_EXTERNAL":
        analogy_prompt = (
            f"The student previously mastered: '{analogy_anchor.get('title', '')}' in domain '{analogy_anchor.get('domain', '')}'. "
            "Map this familiar concept onto the target concept as a bridge analogy."
        )

    active_attempts = 0
    for node in session_state.concept_graph:
        if node.concept_id == session_state.active_concept_id:
            active_attempts = node.attempts
            break

    nudge_context = ""
    if active_attempts > 1:
        nudge_context = (
            f"The student has attempted this concept {active_attempts} times already. "
            "Provide a crisp, compassionate metacognitive study tip advising them to trace concrete inputs "
            "or visualize execution instead of passive re-reading."
        )
    elif session_state.detected_misconceptions:
        nudge_context = (
            f"The student has known misconceptions: {misconceptions_summary}. "
            "Address this subtly in the study_habit_nudge."
        )

    analogy_req = (
        "3. bridge_analogy: REQUIRED for ENRICHED_EXTERNAL. Create a concrete, intuitive real-world or cross-domain analogy "
        "(source_concept, target_concept, mapping) explaining the concept through a familiar system."
        if scope == "ENRICHED_EXTERNAL"
        else "3. bridge_analogy: Leave null unless grounded in source excerpts or prior memory."
    )

    prompt = (
        f"Domain: {session_state.domain}\n"
        f"Primary Topic: {session_state.topic_title}\n"
        f"Active Concept: {active_concept.get('title', 'Core Concept')} [{active_concept.get('concept_id', '')}]\n"
        f"Summary Hook: {active_concept.get('summary_hook', '')}\n"
        f"Prerequisites: {prereq_summary}\n"
        f"Next Goal: {next_goal.get('title', 'Next Tier') if next_goal else 'Mastery'}\n"
        f"Strategy Weights: {session_state.domain_strategy_weights}\n\n"
        f"{scope_rules}\n\n"
        f"SOURCE RESOURCE EXCERPTS:\n{chunks_text}\n\n"
        f"{analogy_prompt}\n"
        f"{nudge_context}\n\n"
        "Generate the Foundation Board contents:\n"
        "1. bullet_breakdown: 3 to 5 clear bullet points dissecting the mechanism (cite source excerpts if present).\n"
        "2. raw_mermaid_diagram: A clean flowchart TD diagram illustrating state/causal flow.\n"
        f"{analogy_req}\n"
        "4. study_habit_nudge: 1 actionable metacognitive tip."
    )

    try:
        structured_resp: StructuredFoundationResponse = client.generate_structured(
            prompt=prompt,
            schema=StructuredFoundationResponse,
            tier="reasoning",
            system_instruction=system_instruction,
            temperature=0.2,
        )

        sanitized_chart = sanitize_mermaid_diagram(structured_resp.raw_mermaid_diagram)

        bridge_dict = None
        if structured_resp.bridge_analogy:
            bridge_dict = {
                "source_concept": structured_resp.bridge_analogy.source_concept,
                "target_concept": structured_resp.bridge_analogy.target_concept,
                "mapping": structured_resp.bridge_analogy.mapping,
            }
        elif scope == "ENRICHED_EXTERNAL":
            active_title = active_concept.get("title", session_state.topic_title)
            bridge_dict = {
                "source_concept": "Everyday Mechanical Equilibrium",
                "target_concept": active_title,
                "mapping": f"Just like a pendulum always seeks its lowest resting point and counteracts any displacement, {active_title} dynamically balances internal forces.",
            }

        return FoundationBoardPayload(
            ui_component="FOUNDATION_BOARD",
            concept_id=session_state.active_concept_id,
            bullet_breakdown=structured_resp.bullet_breakdown,
            mermaid_diagram=sanitized_chart,
            bridge_analogy=bridge_dict,
            interactive_lab=None,  # Attached downstream by Agent 5 if applicable
            study_habit_nudge=structured_resp.study_habit_nudge,
        )

    except Exception as e:
        logger.error("Agent 4: LLM foundation generation failed (%s). Using robust pedagogical fallback.", e)
        active_title = active_concept.get("title", session_state.topic_title)
        safe_chart = (
            "flowchart TD\n"
            f'    A["Initial State: {active_title}"] --> B["Decomposition into Sub-Problems"]\n'
            '    B --> C["Convergence Condition / Base Case"]\n'
            '    C --> D["Synthesis & State Resolution"]'
        )
        return FoundationBoardPayload(
            ui_component="FOUNDATION_BOARD",
            concept_id=session_state.active_concept_id,
            bullet_breakdown=[
                f"{active_title} decomposes complex scenarios into structured, predictable sub-units.",
                "Each stage transitions deterministically based on defined input constraints.",
                "Without explicit terminating conditions, execution risks infinite loops or memory overflow.",
                "State unwinds predictably once terminal criteria are satisfied.",
            ],
            mermaid_diagram=safe_chart,
            bridge_analogy={
                "source_concept": "Building Blocks Hierarchy",
                "target_concept": active_title,
                "mapping": "Just as complex structures require a stable foundational layer before higher tiers can stand, this concept resolves basic preconditions first.",
            } if scope == "ENRICHED_EXTERNAL" else None,
            interactive_lab=None,
            study_habit_nudge="Try tracing a minimal concrete example with pen and paper before reviewing code.",
        )
