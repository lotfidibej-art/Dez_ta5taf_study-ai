import logging
import re
from typing import Dict, List, Optional
import networkx as nx
import numpy as np
from pydantic import BaseModel, Field

from app.db.migrations import get_db_connection
from app.schemas.contracts import ConceptNodeState, ResourceChunk
from app.services.llm_client import GeminiLLMClient, get_llm_client
from app.services.local_models import LocalMLService

logger = logging.getLogger(__name__)


class ExtractedConceptItem(BaseModel):
    concept_id: str = Field(..., description="Unique slug like 'concept_base_case_termination'")
    title: str = Field(..., description="Human-readable concept title")
    prerequisites: List[str] = Field(
        default_factory=list,
        description="List of parent concept_ids that must be understood before this concept",
    )
    summary_hook: str = Field(
        ...,
        description="1-2 sentence core mental model hook capturing the intuition",
    )


class ExtractedCurriculum(BaseModel):
    concepts: List[ExtractedConceptItem] = Field(
        ...,
        description="Structured curriculum of 4 to 8 concepts with prerequisite dependencies",
    )


def slugify(text: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return "concept_" + re.sub(r"[-\s]+", "_", cleaned)[:40]


def extract_concept_dag(
    session_id: str,
    topic_title: str,
    domain: str,
    chunks: List[ResourceChunk],
    llm: Optional[GeminiLLMClient] = None,
) -> List[ConceptNodeState]:
    """Agent 1 (Ingestion & Concept Extractor):

    Uses Gemini fast tier to extract a 4-8 concept learning dependency graph from source chunks
    or canonical topic curriculum, enforces DAG acyclicity via NetworkX, and links source chunks
    to concepts in PostgreSQL via cosine similarity.
    """
    client = llm or get_llm_client()

    context_text = ""
    if chunks:
        # Assemble truncated high-signal context snippet up to 12,000 characters
        context_parts = []
        for c in chunks[:15]:
            context_parts.append(f"[{c.source_name} - {c.source_location}]\n{c.content}")
        context_text = "\n\n".join(context_parts)[:12000]

    system_instruction = (
        "You are Agent 1 (Curriculum & Knowledge Graph Architect). "
        "Extract 4 to 7 progressive, atomic concept nodes for the requested topic. "
        "Every concept must have a clean slug 'concept_id', concise 'title', 'summary_hook', "
        "and logical 'prerequisites' referencing earlier concept_ids. "
        "The graph MUST be a Directed Acyclic Graph (DAG) with foundational concepts having no prerequisites."
    )

    if context_text:
        prompt = (
            f"Topic: {topic_title}\nDomain: {domain}\n\n"
            f"SOURCE MATERIAL EXCERPTS:\n{context_text}\n\n"
            "Analyze the source materials and construct the concept dependency graph. "
            "Ensure foundational concepts lead into intermediate and advanced ones."
        )
    else:
        prompt = (
            f"Topic: {topic_title}\nDomain: {domain}\n\n"
            "No external files were provided. Construct a canonical, highly pedagogical curriculum "
            "decomposing this topic into 4 to 6 sequential concepts with clear prerequisite dependencies."
        )

    extracted_curriculum: ExtractedCurriculum
    try:
        extracted_curriculum = client.generate_structured(
            prompt=prompt,
            schema=ExtractedCurriculum,
            tier="fast",
            system_instruction=system_instruction,
            temperature=0.2,
        )
    except Exception as e:
        logger.error("LLM extraction failed (%s). Generating fallback curriculum.", e)
        # Fallback curriculum
        safe_topic_slug = slugify(topic_title)
        extracted_curriculum = ExtractedCurriculum(
            concepts=[
                ExtractedConceptItem(
                    concept_id=f"{safe_topic_slug}_foundations",
                    title=f"{topic_title}: Core Foundations",
                    prerequisites=[],
                    summary_hook="Foundational principles, definitions, and mental models.",
                ),
                ExtractedConceptItem(
                    concept_id=f"{safe_topic_slug}_mechanism",
                    title=f"{topic_title}: Mechanics & Structure",
                    prerequisites=[f"{safe_topic_slug}_foundations"],
                    summary_hook="Step-by-step structural execution and decomposition.",
                ),
                ExtractedConceptItem(
                    concept_id=f"{safe_topic_slug}_edge_cases",
                    title=f"{topic_title}: Edge Cases & Optimization",
                    prerequisites=[f"{safe_topic_slug}_mechanism"],
                    summary_hook="Subtle misconceptions, failure modes, and performance trade-offs.",
                ),
            ]
        )

    raw_concepts = extracted_curriculum.concepts
    logger.info("Agent 1 extracted %d raw concept nodes for %s", len(raw_concepts), topic_title)

    # ==========================================================================
    # NetworkX DAG Validation & Deterministic Cycle Breaking
    # ==========================================================================
    G = nx.DiGraph()
    concept_map: Dict[str, ExtractedConceptItem] = {}

    for c in raw_concepts:
        # Standardize slug
        c_id = c.concept_id if c.concept_id.startswith("concept_") else f"concept_{c.concept_id}"
        c.concept_id = c_id
        concept_map[c_id] = c
        G.add_node(c_id)

    valid_ids = set(concept_map.keys())

    for c_id, item in concept_map.items():
        for p in item.prerequisites:
            p_id = p if p.startswith("concept_") else f"concept_{p}"
            if p_id in valid_ids and p_id != c_id:
                G.add_edge(p_id, c_id)

    # Break any circular edges deterministically
    while not nx.is_directed_acyclic_graph(G):
        try:
            cycle = nx.find_cycle(G, orientation="original")
            u, v = cycle[-1][:2]
            logger.warning("Breaking circular prerequisite edge in DAG: %s -> %s", u, v)
            G.remove_edge(u, v)
        except Exception:
            break

    # Topological sorting of nodes
    try:
        topo_order = list(nx.topological_sort(G))
    except Exception:
        topo_order = list(concept_map.keys())

    # Formulate final ConceptNodeState list
    final_nodes: List[ConceptNodeState] = []
    first_active = True

    for node_id in topo_order:
        item = concept_map.get(node_id)
        if not item:
            continue
        prereqs = list(G.predecessors(node_id))
        in_degree = len(prereqs)

        # Roots (in-degree 0) start as ACTIVE, others LOCKED
        status = "ACTIVE" if (in_degree == 0 and first_active) else ("ACTIVE" if in_degree == 0 else "LOCKED")
        if in_degree == 0:
            first_active = False

        final_nodes.append(
            ConceptNodeState(
                concept_id=node_id,
                title=item.title,
                prerequisites=prereqs,
                mastery_rating=0.0,
                status=status,
                attempts=0,
                summary_hook=item.summary_hook,
            )
        )

    # Ensure at least one node is ACTIVE
    if final_nodes and not any(n.status == "ACTIVE" for n in final_nodes):
        final_nodes[0].status = "ACTIVE"

    # ==========================================================================
    # Persist Concept DAG Nodes to PostgreSQL concept_nodes & Link Resource Chunks
    # ==========================================================================
    if final_nodes:
        try:
            import json
            ml_service = LocalMLService.get_instance()
            concept_texts = [f"{n.title}. {n.summary_hook or ''}" for n in final_nodes]
            concept_embeddings = np.array(ml_service.embed_text(concept_texts))  # Shape (N, 384)

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # 1. Persist DAG concept nodes to PostgreSQL concept_nodes table
                    for i, node in enumerate(final_nodes):
                        emb_list = concept_embeddings[i].tolist()
                        metadata = {
                            "concept_id": node.concept_id,
                            "prerequisites": node.prerequisites,
                            "summary_hook": node.summary_hook,
                            "session_id": session_id,
                            "mastery_rating": node.mastery_rating,
                            "status": node.status,
                            "attempts": node.attempts,
                        }
                        cur.execute(
                            """
                            INSERT INTO concept_nodes (domain, concept_name, content, embedding, metadata)
                            VALUES (%s, %s, %s, %s, %s)
                            """,
                            (
                                domain,
                                node.title,
                                f"{node.title}: {node.summary_hook or ''}",
                                emb_list,
                                json.dumps(metadata),
                            ),
                        )

                    # 2. Link Resource Chunks in PostgreSQL to closest Concept Node
                    if chunks:
                        cur.execute(
                            "SELECT chunk_id, embedding FROM resource_chunks WHERE session_id = %s",
                            (session_id,),
                        )
                        chunk_rows = cur.fetchall()

                        for chunk_id, chunk_emb in chunk_rows:
                            if chunk_emb is not None:
                                c_emb = np.array(list(chunk_emb), dtype=np.float32)
                                sims = np.dot(concept_embeddings, c_emb)
                                best_idx = int(np.argmax(sims))
                                best_concept_id = final_nodes[best_idx].concept_id
                                cur.execute(
                                    "UPDATE resource_chunks SET concept_id = %s WHERE chunk_id = %s",
                                    (best_concept_id, chunk_id),
                                )
            logger.info("Persisted %d DAG concept nodes and linked %d resource chunks in PostgreSQL", len(final_nodes), len(chunks))
        except Exception as e:
            logger.warning("Failed to persist concept nodes or link chunks in PostgreSQL: %s", e, exc_info=True)

    return final_nodes
