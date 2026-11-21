-- ==============================================================================
-- Adaptive AI Learning Platform - Initial Database Schema
-- Enables pgvector extension and initializes persistence models.
-- ==============================================================================

-- 1. Enable pgvector and UUID extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Students Table
CREATE TABLE IF NOT EXISTS students (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 3. Student Domain Profiles (Multi-armed bandit pedagogical technique weights)
CREATE TABLE IF NOT EXISTS student_domain_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    domain VARCHAR(100) NOT NULL,
    technique_weights JSONB NOT NULL DEFAULT '{"visual": 1.0, "analogy": 1.0, "faded_example": 1.0, "socratic": 1.0, "protege": 1.0}'::jsonb,
    mastered_concepts JSONB NOT NULL DEFAULT '[]'::jsonb,
    domain_mastery_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_student_domain UNIQUE (student_id, domain)
);

CREATE INDEX IF NOT EXISTS idx_student_domain_lookup 
    ON student_domain_profiles (student_id, domain);

-- 4. Concept Nodes Table (Knowledge graph nodes with 384-d BGE-small embeddings)
CREATE TABLE IF NOT EXISTS concept_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain VARCHAR(100) NOT NULL,
    concept_name VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    embedding vector(384),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Fast Approximate Nearest Neighbor Cosine Index via HNSW
CREATE INDEX IF NOT EXISTS idx_concept_nodes_embedding 
    ON concept_nodes USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_concept_nodes_domain 
    ON concept_nodes (domain);

CREATE INDEX IF NOT EXISTS idx_concept_nodes_name 
    ON concept_nodes (concept_name);

-- 5. Session Resumes Table (Scannable end-of-session summaries & mental models)
CREATE TABLE IF NOT EXISTS session_resumes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    domain VARCHAR(100) NOT NULL,
    session_mode VARCHAR(50) NOT NULL,
    summary TEXT NOT NULL,
    mental_model TEXT,
    winning_analogies JSONB NOT NULL DEFAULT '[]'::jsonb,
    misconceptions_conquered JSONB NOT NULL DEFAULT '[]'::jsonb,
    analytics JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_session_resumes_student 
    ON session_resumes (student_id);

CREATE INDEX IF NOT EXISTS idx_session_resumes_domain 
    ON session_resumes (domain);

-- 6. Telemetry Events Table (Granular student interaction & prosody telemetry logs)
CREATE TABLE IF NOT EXISTS telemetry_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID REFERENCES students(id) ON DELETE SET NULL,
    session_id VARCHAR(100) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_telemetry_session 
    ON telemetry_events (session_id);

CREATE INDEX IF NOT EXISTS idx_telemetry_event_type 
    ON telemetry_events (event_type);

CREATE INDEX IF NOT EXISTS idx_telemetry_created_at 
    ON telemetry_events (created_at DESC);
