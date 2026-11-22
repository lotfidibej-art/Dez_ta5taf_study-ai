import json
import logging
from typing import Dict, List, Tuple

import numpy as np

from app.db.migrations import get_db_connection
from app.schemas.contracts import ConceptNodeState
from app.services.local_models import LocalMLService

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS = {
    "visual": 1.0,
    "analogy": 1.0,
    "faded_example": 1.0,
    "socratic": 1.0,
    "protege": 1.0,
}


def hydrate_learner_profile(
    student_id: str,
    domain: str,
    concept_graph: List[ConceptNodeState],
) -> Tuple[Dict[str, float], List[ConceptNodeState], List[Dict[str, str]]]:
    """Agent 2 (Domain Profiler):

    1. Loads or initializes multi-armed bandit technique weights for (student_id, domain).
    2. Identifies previously mastered concepts across all domains.
    3. Pre-marks new concepts as MASTERED (0.90) if cosine similarity > 0.88 to an already-mastered node.
    4. Retrieves top 5 cross-domain anchor concepts to power bridge analogies.
    """
    domain_weights = dict(DEFAULT_WEIGHTS)
    mastered_anchors: List[Dict[str, str]] = []

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 1. Fetch or create domain profile
                # Check if students row exists for foreign key constraint or insert student if needed
                cur.execute(
                    """
                    SELECT id FROM students WHERE id::text = %s OR email = %s LIMIT 1
                    """,
                    (student_id, f"{student_id}@student.local"),
                )
                student_row = cur.fetchone()
                db_student_id = student_row[0] if student_row else None

                if not db_student_id:
                    # Insert student record if possible
                    try:
                        cur.execute(
                            """
                            INSERT INTO students (id, email, name)
                            VALUES (gen_random_uuid(), %s, %s)
                            ON CONFLICT (email) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
                            RETURNING id
                            """,
                            (f"{student_id}@student.local", student_id),
                        )
                        db_student_id = cur.fetchone()[0]
                    except Exception as e:
                        logger.warning("Could not auto-provision student record: %s", e)

                if db_student_id:
                    cur.execute(
                        """
                        SELECT technique_weights 
                        FROM student_domain_profiles 
                        WHERE student_id = %s AND domain = %s
                        """,
                        (db_student_id, domain),
                    )
                    profile_row = cur.fetchone()
                    if profile_row and profile_row[0]:
                        domain_weights = profile_row[0]
                    else:
                        # Insert default profile row
                        cur.execute(
                            """
                            INSERT INTO student_domain_profiles 
                                (student_id, domain, technique_weights, mastered_concepts, domain_mastery_score)
                            VALUES (%s, %s, %s, %s, 0.0)
                            ON CONFLICT (student_id, domain) DO NOTHING
                            """,
                            (
                                db_student_id,
                                domain,
                                json.dumps(DEFAULT_WEIGHTS),
                                json.dumps([]),
                            ),
                        )

                # 2. Check concept_nodes for prior mastered concepts across all domains
                cur.execute(
                    """
                    SELECT domain, concept_name, content, embedding 
                    FROM concept_nodes 
                    WHERE (metadata->>'mastery_rating')::float >= 0.85
                    LIMIT 50
                    """
                )
                prior_mastered_rows = cur.fetchall()

                # Also inspect past session_resumes for winning mental models & concepts
                cur.execute(
                    """
                    SELECT domain, mental_model, winning_analogies, misconceptions_conquered 
                    FROM session_resumes 
                    ORDER BY created_at DESC 
                    LIMIT 10
                    """
                )
                resume_rows = cur.fetchall()

                for r in resume_rows:
                    r_domain, r_model, r_analogies, _ = r
                    if r_model:
                        mastered_anchors.append({
                            "domain": r_domain,
                            "concept": r_domain.replace("_", " ").title(),
                            "summary_hook": r_model[:120],
                        })

                # If no DB records yet, provide high-value cross-domain anchor seeds
                if not mastered_anchors:
                    mastered_anchors = [
                        {
                            "domain": "everyday_physics",
                            "concept": "Water Pressure & Piping",
                            "summary_hook": "Potential energy pushing fluid through constrictions, balancing flow rate and pressure.",
                        },
                        {
                            "domain": "cooking",
                            "concept": "Recipe Assembly Line",
                            "summary_hook": "Executing sequential prep steps and parallel ingredient mixing before the oven step.",
                        },
                        {
                            "domain": "transportation",
                            "concept": "Highway Traffic Merging",
                            "summary_hook": "Buffer zones, bottlenecks, and throughput limits when lanes compress.",
                        },
                        {
                            "domain": "biology",
                            "concept": "Enzyme Lock-and-Key Catalysis",
                            "summary_hook": "Specific structural fitting that lowers the activation threshold for a reaction.",
                        },
                    ]

                # 3. Check cosine similarity against prior mastered concepts if any
                if prior_mastered_rows and concept_graph:
                    ml_service = LocalMLService.get_instance()
                    new_concept_texts = [f"{n.title}. {n.summary_hook or ''}" for n in concept_graph]
                    new_embeddings = np.array(ml_service.embed_text(new_concept_texts))  # Shape (M, 384)

                    for p_domain, p_name, p_content, p_emb in prior_mastered_rows:
                        if p_emb is not None:
                            if hasattr(p_emb, "to_numpy"):
                                prior_vec = p_emb.to_numpy()
                            elif hasattr(p_emb, "to_list"):
                                prior_vec = np.array(p_emb.to_list(), dtype=np.float32)
                            else:
                                prior_vec = np.array(p_emb, dtype=np.float32)
                            sims = np.dot(new_embeddings, prior_vec)
                            for idx, sim in enumerate(sims):
                                if sim > 0.88:
                                    logger.info(
                                        "Pre-marking concept '%s' as MASTERED (similarity=%.3f to mastered '%s')",
                                        concept_graph[idx].title,
                                        sim,
                                        p_name,
                                    )
                                    concept_graph[idx].status = "MASTERED"
                                    concept_graph[idx].mastery_rating = 0.90

    except Exception as e:
        logger.warning("Domain profiler query error: %s. Using default weights.", e)

    return domain_weights, concept_graph, mastered_anchors[:5]
