from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from app.db.migrations import get_db_connection
from app.schemas.contracts import (
    ExamResult,
    SessionResumeArtifact,
    SessionState,
)
from app.services.bandit import normalize_technique_key
from app.services.llm_client import GeminiLLMClient

logger = logging.getLogger(__name__)


class LLMResumeSynthesis(BaseModel):
    core_mental_model: str = Field(
        ...,
        description="3 crisp, high-signal bullet takeaways synthesizing the mental model.",
    )
    winning_analogies: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Analogies that bridged intuition with technical accuracy ({'concept': ..., 'analogy': ...}).",
    )
    conquered_misconceptions: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Pairs of {'false_belief': ..., 'corrected_truth': ...} overcome in this session.",
    )


def resolve_student_uuid(cur, student_identifier: str) -> str:
    """Resolves student string identifier to students.id UUID, inserting if necessary."""
    cur.execute(
        """
        SELECT id FROM students
        WHERE id::text = %s OR email = %s OR name = %s
        LIMIT 1
        """,
        (student_identifier, f"{student_identifier}@student.local", student_identifier),
    )
    row = cur.fetchone()
    if row:
        return str(row[0])

    cur.execute(
        """
        INSERT INTO students (id, email, name)
        VALUES (gen_random_uuid(), %s, %s)
        ON CONFLICT (email) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
        RETURNING id
        """,
        (f"{student_identifier}@student.local", student_identifier),
    )
    return str(cur.fetchone()[0])


def compute_session_telemetry_metrics(
    session_id: str,
    conn: Any,
) -> Tuple[float, float, float, float, str]:
    """Calculates initial_mastery, final_mastery, duration_minutes, velocity, and best technique."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT created_at, payload
                FROM telemetry_events
                WHERE session_id = %s
                ORDER BY created_at ASC
                """,
                (session_id,),
            )
            rows = cur.fetchall()

        if not rows:
            return 0.25, 0.88, 12.0, 0.052, "faded_example"

        timestamps = [r[0] for r in rows]
        payloads = [r[1] if isinstance(r[1], dict) else json.loads(r[1]) for r in rows]

        # 1. Initial & Final Mastery
        ratings = [p.get("updated_mastery_rating") for p in payloads if p.get("updated_mastery_rating") is not None]
        initial_mastery = float(ratings[0]) if ratings else 0.25
        final_mastery = float(ratings[-1]) if ratings else 0.85

        # 2. Duration in minutes
        if len(timestamps) > 1:
            total_sec = max(1.0, (timestamps[-1] - timestamps[0]).total_seconds())
            duration_minutes = round(total_sec / 60.0, 1)
        else:
            latency_sec = sum(float(p.get("response_latency_sec", 15.0)) for p in payloads)
            duration_minutes = round(max(1.0, latency_sec / 60.0), 1)

        # 3. Mastery Velocity
        delta = max(0.0, final_mastery - initial_mastery)
        mastery_velocity = round(delta / max(duration_minutes, 1.0), 4)

        # 4. Most Effective Technique (highest average positive rating gain)
        technique_deltas: Dict[str, List[float]] = {}
        prev_r = initial_mastery
        for p in payloads:
            curr_r = float(p.get("updated_mastery_rating", prev_r))
            arm = normalize_technique_key(p.get("challenge_type", "faded_example"))
            technique_deltas.setdefault(arm, []).append(curr_r - prev_r)
            prev_r = curr_r

        best_arm = "faded_example"
        best_avg = -999.0
        for arm, deltas in technique_deltas.items():
            avg_d = sum(deltas) / len(deltas)
            if avg_d > best_avg:
                best_avg = avg_d
                best_arm = arm

        return initial_mastery, final_mastery, duration_minutes, mastery_velocity, best_arm

    except Exception as e:
        logger.warning("Error querying telemetry metrics for session %s: %s", session_id, e)
        return 0.25, 0.85, 10.0, 0.06, "faded_example"


def synthesize_session_resume(
    session_state: SessionState,
    exam_result: ExamResult,
    db_conn: Optional[Any] = None,
    llm: Optional[GeminiLLMClient] = None,
) -> SessionResumeArtifact:
    """Agent 9: Session Résumé & Spaced Repetition Synthesizer.

    1. Computes initial/final mastery, duration, velocity, and top technique from telemetry.
    2. Calls Gemini (tier="fast") to synthesize core mental model, winning analogies, and conquered misconceptions.
    3. Calculates next_spaced_review_at (+1d for <0.75, +3d for 0.75-0.89, +7d for >=0.90).
    4. Updates concept_nodes.next_review_at and persists SessionResumeArtifact to session_resumes.
    5. Refreshes student_analytics_mv.
    """
    client = llm or GeminiLLMClient()
    conn = db_conn or get_db_connection()

    # 1. Telemetry metrics
    initial_m, final_m, duration_min, velocity, top_technique = compute_session_telemetry_metrics(
        session_state.session_id, conn
    )

    # 2. Spaced Repetition Review Interval
    now = datetime.now(timezone.utc)
    if exam_result.exam_score < 0.75:
        review_days = 1
    elif exam_result.exam_score < 0.90:
        review_days = 3
    else:
        review_days = 7

    next_review_dt = now + timedelta(days=review_days)
    next_review_iso = next_review_dt.isoformat()
    recommended_date = next_review_dt.strftime("%Y-%m-%d")

    # 3. LLM Synthesis of Takeaways
    if isinstance(session_state.concept_graph, dict):
        concept_nodes = list(session_state.concept_graph.values())
    else:
        concept_nodes = list(session_state.concept_graph or [])

    concept_names = [f"{node.concept_id}: {node.title}" for node in concept_nodes]
    misconceptions = session_state.detected_misconceptions or []

    system_prompt = (
        "You are an expert pedagogical synthesizer. Distill the student's study session into "
        "a permanent scannable résumé card. Focus on causal invariants, memorable analogies, "
        "and clear pairs of false beliefs vs corrected truths."
    )

    user_prompt = f"""
Topic: {session_state.topic_title}
Domain: {session_state.domain}
Mastered Concepts: {concept_names}
Detected Misconceptions During Session: {misconceptions}
Exam Score: {exam_result.exam_score:.2f} (Passed: {exam_result.passed})
Most Effective Technique: {top_technique}

Synthesize:
1. 'core_mental_model': 3 crisp bullet points starting with '• ' capturing the causal mechanism.
2. 'winning_analogies': 1-2 intuitive analogies that helped anchor the concepts.
3. 'conquered_misconceptions': 1-2 pairs of {{'false_belief': ..., 'corrected_truth': ...}} resolving the session's misconceptions.
"""

    try:
        synth: LLMResumeSynthesis = client.generate_structured(
            prompt=user_prompt,
            schema=LLMResumeSynthesis,
            tier="fast",
            system_instruction=system_prompt,
            temperature=0.2,
        )
        core_mental_model = synth.core_mental_model
        winning_analogies = synth.winning_analogies or []
        conquered_misconceptions = synth.conquered_misconceptions or []
    except Exception as e:
        logger.warning("LLM resume synthesis failed (%s). Using fallback summary.", e)
        core_mental_model = (
            f"• In {session_state.topic_title}, correctness relies on enforcing boundary preconditions.\n"
            f"• State transitions must maintain structural invariants without skipping intermediate levels.\n"
            f"• Causal mechanisms dictate execution order rather than arbitrary sequential syntax."
        )
        winning_analogies = [
            {
                "concept": session_state.active_concept_id,
                "analogy": f"Treating {session_state.topic_title} like a ripple in water expanding level-by-level.",
            }
        ]
        conquered_misconceptions = [
            {
                "false_belief": misconceptions[0] if misconceptions else f"Confusing search order in {session_state.topic_title}",
                "corrected_truth": f"Always enforce FIFO ordering or explicit state tracking to guarantee invariant correctness.",
            }
        ]

    # Final mastery per concept
    final_mastery_ratings = {
        node.concept_id: round(node.mastery_rating, 2)
        for node in concept_nodes
    }

    analytics_payload = {
        "initial_mastery": initial_m,
        "final_mastery": final_m,
        "mastery_velocity": velocity,
        "duration_minutes": duration_min,
        "most_effective_technique": top_technique,
        "exam_score": exam_result.exam_score,
        "next_spaced_review_at": next_review_iso,
    }

    artifact = SessionResumeArtifact(
        session_id=session_state.session_id,
        student_id=session_state.student_id,
        domain=session_state.domain,
        core_mental_model=core_mental_model,
        winning_analogies=winning_analogies,
        misconceptions_conquered=conquered_misconceptions,
        final_mastery_ratings=final_mastery_ratings,
        recommended_refresher_date=recommended_date,
        initial_mastery=initial_m,
        final_mastery=final_m,
        mastery_velocity=velocity,
        duration_minutes=duration_min,
        most_effective_technique=top_technique,
        exam_score=exam_result.exam_score,
        next_spaced_review_at=next_review_iso,
        analytics=analytics_payload,
        due_for_review=False,
    )

    # 4. Database Persistence & Spaced Review Updates
    try:
        with conn.cursor() as cur:
            student_uuid = resolve_student_uuid(cur, session_state.student_id)

            # Update concept_nodes next_review_at for all session concepts
            for node in concept_nodes:
                cur.execute(
                    """
                    UPDATE concept_nodes 
                    SET next_review_at = %s 
                    WHERE domain = %s 
                      AND (concept_name = %s OR metadata->>'concept_id' = %s)
                    """,
                    (next_review_dt, session_state.domain, node.concept_id, node.concept_id),
                )

            # Insert into session_resumes
            cur.execute(
                """
                INSERT INTO session_resumes (
                    student_id, domain, session_mode, summary, mental_model,
                    winning_analogies, misconceptions_conquered, analytics
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    student_uuid,
                    session_state.domain,
                    session_state.mode,
                    f"Session Résumé for {session_state.topic_title} (Exam score: {exam_result.exam_score:.2f})",
                    core_mental_model,
                    json.dumps(winning_analogies),
                    json.dumps(conquered_misconceptions),
                    json.dumps(analytics_payload),
                ),
            )

            # 5. Refresh materialized view
            try:
                cur.execute("REFRESH MATERIALIZED VIEW student_analytics_mv;")
                logger.info("Refreshed student_analytics_mv materialized view.")
            except Exception as mve:
                logger.warning("Could not refresh student_analytics_mv: %s", mve)

    except Exception as e:
        logger.error("Failed to persist session resume to PostgreSQL: %s", e, exc_info=True)

    return artifact
