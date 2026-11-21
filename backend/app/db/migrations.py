import logging
import os
from typing import Any, Optional

try:
    import psycopg
    from pgvector.psycopg import register_vector
    _PSYCOPG_AVAILABLE = True
except ImportError:
    psycopg = None  # type: ignore
    register_vector = None  # type: ignore
    _PSYCOPG_AVAILABLE = False

logger = logging.getLogger(__name__)

MIGRATION_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS resource_chunks (
    chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    student_id TEXT NOT NULL,
    concept_id TEXT,
    content TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_location TEXT NOT NULL,
    embedding vector(384),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_resource_chunks_embedding 
    ON resource_chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_resource_chunks_session 
    ON resource_chunks (session_id);

CREATE INDEX IF NOT EXISTS idx_resource_chunks_concept 
    ON resource_chunks (concept_id);

CREATE TABLE IF NOT EXISTS telemetry_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id TEXT,
    session_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_telemetry_session 
    ON telemetry_events (session_id);

CREATE INDEX IF NOT EXISTS idx_telemetry_event_type 
    ON telemetry_events (event_type);
"""


def get_db_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql://learner:learner_pass@postgres:5432/adaptive_learning",
    )


def get_db_connection(db_url: Optional[str] = None) -> Any:
    if not _PSYCOPG_AVAILABLE:
        raise RuntimeError("psycopg / pgvector is not installed in the current environment.")
    url = db_url or get_db_url()
    conn = psycopg.connect(url, autocommit=True)
    register_vector(conn)
    return conn


def run_migrations(db_url: Optional[str] = None) -> None:
    """Executes idempotent startup migrations creating resource_chunks and vector indexes."""
    if not _PSYCOPG_AVAILABLE:
        logger.warning("psycopg is not installed. Skipping database migrations.")
        return
    url = db_url or get_db_url()
    logger.info("Running database migrations on %s...", url.split("@")[-1])
    try:
        with psycopg.connect(url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(MIGRATION_SQL)
        logger.info("Database migrations executed successfully.")
    except Exception as e:
        logger.error("Failed to run database migrations: %s", e, exc_info=True)
        raise
