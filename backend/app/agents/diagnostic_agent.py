import logging
from typing import List, Optional
import networkx as nx
from pydantic import BaseModel, Field

from app.orchestrator.graph_utils import build_networkx_dag
from app.schemas.contracts import ConceptNodeState, DiagnosticQuestion
from app.services.llm_client import GeminiLLMClient, get_llm_client

logger = logging.getLogger(__name__)


class DiagnosticQuestionBatch(BaseModel):
    questions: List[DiagnosticQuestion] = Field(
        ...,
        description="List of exactly 3 diagnostic questions spanning foundational, intermediate, and advanced nodes.",
    )


def select_diagnostic_target_nodes(concept_graph: List[ConceptNodeState]) -> List[tuple[ConceptNodeState, str]]:
    """Inspects DAG topological layers and selects 3 target nodes: foundational, intermediate, and advanced."""
    if not concept_graph:
        return []

    if len(concept_graph) <= 3:
        tiers = ["FOUNDATIONAL", "INTERMEDIATE", "ADVANCED"]
        return [(node, tiers[i if i < len(tiers) else -1]) for i, node in enumerate(concept_graph)]

    G = build_networkx_dag(concept_graph)
    node_map = {n.concept_id: n for n in concept_graph}

    # Calculate shortest path depth from roots
    roots = [n for n in G.nodes if G.in_degree(n) == 0]
    depths = {}
    for node in G.nodes:
        min_depth = 999
        for r in roots:
            try:
                d = nx.shortest_path_length(G, r, node)
                if d < min_depth:
                    min_depth = d
            except nx.NetworkXNoPath:
                pass
        depths[node] = min_depth if min_depth != 999 else 0

    sorted_by_depth = sorted(depths.items(), key=lambda x: x[1])

    # 1. Foundational node (depth 0)
    foundational_id = sorted_by_depth[0][0]

    # 2. Advanced node (deepest node / leaf)
    advanced_id = sorted_by_depth[-1][0]
    if advanced_id == foundational_id and len(sorted_by_depth) > 1:
        advanced_id = sorted_by_depth[1][0]

    # 3. Intermediate node (mid-depth)
    mid_idx = len(sorted_by_depth) // 2
    intermediate_id = sorted_by_depth[mid_idx][0]
    if intermediate_id in (foundational_id, advanced_id):
        for candidate, _ in sorted_by_depth:
            if candidate not in (foundational_id, advanced_id):
                intermediate_id = candidate
                break

    targets = [
        (node_map[foundational_id], "FOUNDATIONAL"),
        (node_map[intermediate_id], "INTERMEDIATE"),
        (node_map[advanced_id], "ADVANCED"),
    ]
    return targets


def generate_baseline_diagnostic(
    topic_title: str,
    domain: str,
    concept_graph: List[ConceptNodeState],
    llm: Optional[GeminiLLMClient] = None,
) -> List[DiagnosticQuestion]:
    """Generates 3 concise, open-ended diagnostic questions calibrated across the DAG."""
    targets = select_diagnostic_target_nodes(concept_graph)
    if not targets:
        return []

    client = llm or get_llm_client()

    target_descriptions = "\n".join(
        [
            f"- [{tier}] Concept ID: {node.concept_id} | Title: {node.title} | Hook: {node.summary_hook or 'N/A'}"
            for node, tier in targets
        ]
    )

    prompt = (
        f"Topic: {topic_title}\nDomain: {domain}\n\n"
        "Generate exactly 3 open-ended diagnostic questions to assess the student's baseline understanding. "
        "Each question must target one of these selected nodes:\n"
        f"{target_descriptions}\n\n"
        "Guidelines:\n"
        "1. Foundational question: asks 'why' or 'how', focusing on the core mental model.\n"
        "2. Intermediate question: tests execution mechanics, relations, or step sequencing.\n"
        "3. Advanced question: tests edge cases, failure points, or trade-offs.\n"
        "4. Keep questions concise (1-2 sentences), clear, and provocative."
    )

    system_instruction = (
        "You are Agent 3 (Baseline Diagnostic Architect). "
        "Create 3 distinct, diagnostic open-ended questions corresponding to the 3 target concepts."
    )

    try:
        res = client.generate_structured(
            prompt=prompt,
            schema=DiagnosticQuestionBatch,
            tier="fast",
            system_instruction=system_instruction,
            temperature=0.3,
        )
        # Ensure question_id and matched concept_id are strictly aligned
        validated_questions = []
        for i, q in enumerate(res.questions[:3]):
            matched_node, tier = targets[i if i < len(targets) else -1]
            validated_questions.append(
                DiagnosticQuestion(
                    question_id=f"diag_q_{i + 1}_{matched_node.concept_id}",
                    concept_id=matched_node.concept_id,
                    concept_title=matched_node.title,
                    question_text=q.question_text,
                    depth_tier=tier,  # type: ignore
                )
            )
        return validated_questions

    except Exception as e:
        logger.error("Failed to generate diagnostic via LLM (%s). Using fallback questions.", e)
        # Deterministic fallback
        return [
            DiagnosticQuestion(
                question_id=f"diag_q_1_{targets[0][0].concept_id}",
                concept_id=targets[0][0].concept_id,
                concept_title=targets[0][0].title,
                question_text=f"In your own words, what is the core mechanism of {targets[0][0].title}?",
                depth_tier="FOUNDATIONAL",
            ),
            DiagnosticQuestion(
                question_id=f"diag_q_2_{targets[1][0].concept_id}",
                concept_id=targets[1][0].concept_id,
                concept_title=targets[1][0].title,
                question_text=f"How does {targets[1][0].title} operate step-by-step during typical execution?",
                depth_tier="INTERMEDIATE",
            ),
            DiagnosticQuestion(
                question_id=f"diag_q_3_{targets[2][0].concept_id}",
                concept_id=targets[2][0].concept_id,
                concept_title=targets[2][0].title,
                question_text=f"What subtle bug, limitation, or edge case commonly occurs when implementing {targets[2][0].title}?",
                depth_tier="ADVANCED",
            ),
        ]
