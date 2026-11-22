import json
import logging
from typing import Any, Dict, Optional

from app.db.migrations import get_db_connection

logger = logging.getLogger(__name__)

# Canonical technique keys tracked in domain_strategy_weights & student_domain_profiles
VALID_TECHNIQUES = {"visual", "analogy", "faded_example", "socratic", "protege"}

# Mapping from UI component / technique labels to bandit arm keys
TECHNIQUE_MAPPING: Dict[str, str] = {
    "FOUNDATION_BOARD": "visual",
    "FOUNDATION_BULLETS_ANALOGY": "analogy",
    "FADED_EXAMPLE_WORKSPACE": "faded_example",
    "FADED_WORKED_EXAMPLE": "faded_example",
    "MISCONCEPTION_TRAP": "socratic",
    "PROTEGE_VOICE_STAGE": "protege",
    "visual": "visual",
    "analogy": "analogy",
    "faded_example": "faded_example",
    "socratic": "socratic",
    "protege": "protege",
}


def normalize_technique_key(technique_label: str) -> str:
    """Maps arbitrary pedagogical technique strings to one of the 5 canonical bandit arms."""
    return TECHNIQUE_MAPPING.get(technique_label, "socratic")


def update_bandit_weights(
    student_id: str,
    domain: str,
    last_technique_used: str,
    previous_rating: float,
    updated_rating: float,
    current_weights: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    """Updates multi-armed bandit technique weights using a bounded reinforcement rule.

    Rule:
        technique_reward_delta = updated_comprehension_rating - previous_rating
        new_weight = clamp(old_weight + 0.25 * technique_reward_delta, 0.10, 1.00)

    Persists into PostgreSQL (student_domain_profiles.technique_weights) and returns
    the full updated dictionary to be synced into Redis SessionState.
    """
    weights = dict(current_weights or {
        "visual": 1.0,
        "analogy": 1.0,
        "faded_example": 1.0,
        "socratic": 1.0,
        "protege": 1.0,
    })

    arm_key = normalize_technique_key(last_technique_used)
    reward_delta = updated_rating - previous_rating
    old_weight = float(weights.get(arm_key, 1.0))

    # Bounded learning rate update: clamp between 0.10 and 1.00
    new_weight = max(0.10, min(1.00, round(old_weight + 0.25 * reward_delta, 3)))
    weights[arm_key] = new_weight

    logger.info(
        "Bandit update for student=%s, domain=%s, arm=%s: delta=%.3f, %.3f -> %.3f",
        student_id,
        domain,
        arm_key,
        reward_delta,
        old_weight,
        new_weight,
    )

    # Persist to PostgreSQL student_domain_profiles
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 1. Resolve student UUID
                cur.execute(
                    """
                    SELECT id FROM students 
                    WHERE email = %s OR name = %s
                    LIMIT 1
                    """,
                    (f"{student_id}@student.local", student_id),
                )
                row = cur.fetchone()
                db_student_id = row[0] if row else None

                if not db_student_id:
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

                # 2. Upsert profile with updated weights
                cur.execute(
                    """
                    INSERT INTO student_domain_profiles 
                        (student_id, domain, technique_weights, mastered_concepts, domain_mastery_score)
                    VALUES (%s, %s, %s, '[]'::jsonb, 0.0)
                    ON CONFLICT (student_id, domain) DO UPDATE 
                    SET technique_weights = EXCLUDED.technique_weights,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (db_student_id, domain, json.dumps(weights)),
                )
    except Exception as e:
        logger.warning("Could not persist bandit weights to PostgreSQL (%s). Continuing with in-memory state.", e)

    return weights
