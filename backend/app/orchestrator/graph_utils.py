import logging
from typing import Any, Dict, List, Optional
import networkx as nx

from app.db.migrations import get_db_connection
from app.schemas.contracts import ConceptNodeState, SessionState

logger = logging.getLogger(__name__)


def build_networkx_dag(concept_graph: List[ConceptNodeState]) -> nx.DiGraph:
    """Constructs a NetworkX DiGraph representation of the concept prerequisites."""
    G = nx.DiGraph()
    for node in concept_graph:
        G.add_node(node.concept_id, data=node)

    valid_ids = set(G.nodes)
    for node in concept_graph:
        for p in node.prerequisites:
            if p in valid_ids and p != node.concept_id:
                G.add_edge(p, node.concept_id)

    # Ensure no cycles
    while not nx.is_directed_acyclic_graph(G):
        try:
            cycle = nx.find_cycle(G, orientation="original")
            u, v = cycle[-1][:2]
            G.remove_edge(u, v)
        except Exception:
            break

    return G


def get_next_unlocked_concept(concept_graph: List[ConceptNodeState]) -> str:
    """Deterministically identifies the next unlocked concept node in the DAG.

    A concept is eligible to unlock when all its prerequisites have mastery_rating >= 0.75
    and its own mastery_rating is < 0.85.
    Returns the first eligible concept_id in topological order.
    """
    if not concept_graph:
        return ""

    G = build_networkx_dag(concept_graph)
    node_map = {n.concept_id: n for n in concept_graph}

    try:
        topo_order = list(nx.topological_sort(G))
    except Exception:
        topo_order = [n.concept_id for n in concept_graph]

    for c_id in topo_order:
        node = node_map.get(c_id)
        if not node:
            continue

        # Check all prerequisites
        prereqs_satisfied = True
        for p_id in G.predecessors(c_id):
            p_node = node_map.get(p_id)
            if not p_node or p_node.mastery_rating < 0.75:
                prereqs_satisfied = False
                break

        if prereqs_satisfied and node.mastery_rating < 0.85:
            return c_id

    # If all eligible nodes are mastered, return first non-mastered node, or the last node
    for c_id in topo_order:
        node = node_map.get(c_id)
        if node and node.mastery_rating < 0.85:
            return c_id

    return topo_order[-1]


def get_one_hop_slice(session_state: SessionState) -> Dict[str, Any]:
    """Deterministic 1-Hop Context Slicer.

    Downstream LLMs are NEVER passed the entire concept graph.
    Returns strictly:
    1. active_concept: Target concept metadata + top 2 matching PostgreSQL resource chunks.
    2. immediate_prerequisites: Direct parent nodes and their mastery ratings.
    3. next_unlocked_goal: Immediate unlocked child node in the DAG.
    4. analogy_anchor_from_memory: Top cross-domain anchor concept.
    """
    active_id = session_state.active_concept_id
    concept_map = {n.concept_id: n for n in session_state.concept_graph}
    active_node = concept_map.get(active_id)

    if not active_node and session_state.concept_graph:
        active_node = session_state.concept_graph[0]
        active_id = active_node.concept_id

    G = build_networkx_dag(session_state.concept_graph)

    # 1. Immediate prerequisites (direct in-edges)
    prereq_ids = list(G.predecessors(active_id)) if active_id in G else []
    immediate_prereqs = []
    for p_id in prereq_ids:
        p_node = concept_map.get(p_id)
        if p_node:
            immediate_prereqs.append({
                "concept_id": p_node.concept_id,
                "title": p_node.title,
                "mastery_rating": p_node.mastery_rating,
                "summary_hook": p_node.summary_hook,
            })

    # 2. Next unlocked goal (direct out-edges)
    child_ids = list(G.successors(active_id)) if active_id in G else []
    next_goal = None
    if child_ids:
        child_node = concept_map.get(child_ids[0])
        if child_node:
            next_goal = {
                "concept_id": child_node.concept_id,
                "title": child_node.title,
                "summary_hook": child_node.summary_hook,
            }

    # 3. Fetch top 2 source chunks for the active concept from PostgreSQL
    active_chunks: List[Dict[str, str]] = []
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT content, source_name, source_location 
                    FROM resource_chunks 
                    WHERE session_id = %s AND concept_id = %s 
                    LIMIT 2
                    """,
                    (session_state.session_id, active_id),
                )
                rows = cur.fetchall()
                if not rows:
                    # Fallback to any 2 chunks for this session
                    cur.execute(
                        """
                        SELECT content, source_name, source_location 
                        FROM resource_chunks 
                        WHERE session_id = %s 
                        LIMIT 2
                        """,
                        (session_state.session_id,),
                    )
                    rows = cur.fetchall()

                for r in rows:
                    active_chunks.append({
                        "content": r[0],
                        "source_name": r[1],
                        "source_location": r[2],
                    })
    except Exception as e:
        logger.warning("Error fetching resource chunks for 1-hop slice: %s", e)

    # 4. Cross-domain analogy anchor
    analogy_anchor = (
        session_state.mastered_anchor_concepts[0]
        if session_state.mastered_anchor_concepts
        else None
    )

    return {
        "session_id": session_state.session_id,
        "domain": session_state.domain,
        "topic_title": session_state.topic_title,
        "active_concept": {
            "concept_id": active_node.concept_id if active_node else active_id,
            "title": active_node.title if active_node else active_id,
            "summary_hook": active_node.summary_hook if active_node else None,
            "mastery_rating": active_node.mastery_rating if active_node else 0.0,
            "resource_chunks": active_chunks,
        },
        "immediate_prerequisites": immediate_prereqs,
        "next_unlocked_goal": next_goal,
        "analogy_anchor_from_memory": analogy_anchor,
    }
