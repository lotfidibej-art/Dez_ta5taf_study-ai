import json
import logging
import os
import shutil
import tempfile
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict

import redis
from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.orchestrator.graph import execute_turn
from app.schemas.contracts import (
    ConceptNodeState,
    MockSessionRequest,
    MockSessionResponse,
    SessionState,
)
from app.services.local_models import LocalMLService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("adaptive_platform")

# Initialize Redis client connection
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager: warm up local ML models during container startup."""
    logger.info("Initializing LocalMLService (SentenceTransformer & Whisper)...")
    try:
        LocalMLService.get_instance()
        logger.info("Local ML services pre-loaded and ready.")
    except Exception as e:
        logger.error("Error pre-warming local ML models: %s", e, exc_info=True)
    yield
    logger.info("Application shutdown complete.")


app = FastAPI(
    title="Adaptive AI Learning Platform Backend",
    version="1.0.0",
    description="Orchestrator and local ML inference service for adaptive pedagogy.",
    lifespan=lifespan,
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> Dict[str, str]:
    return {
        "service": "Adaptive AI Learning Platform Backend",
        "status": "operational",
        "version": "1.0.0",
    }


@app.get("/health")
async def healthcheck() -> JSONResponse:
    """Readiness probe checking Postgres (with pgvector), Redis, and local ML models."""
    checks: Dict[str, str] = {
        "postgres": "unknown",
        "vector_extension": "unknown",
        "redis": "unknown",
        "embeddings": "unknown",
        "whisper": "unknown",
    }
    healthy = True

    # 1. PostgreSQL & vector extension check
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://learner:learner_pass@postgres:5432/adaptive_learning",
    )
    try:
        import psycopg

        with psycopg.connect(db_url, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                res = cur.fetchone()
                if res and res[0] == 1:
                    checks["postgres"] = "connected"
                else:
                    checks["postgres"] = "unexpected_response"
                    healthy = False

                cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector';")
                vec_res = cur.fetchone()
                if vec_res and vec_res[0] == 1:
                    checks["vector_extension"] = "installed"
                else:
                    checks["vector_extension"] = "missing"
                    healthy = False
    except Exception as e:
        checks["postgres"] = f"unreachable ({e.__class__.__name__})"
        checks["vector_extension"] = "unreachable"
        healthy = False

    # 2. Redis check
    try:
        if redis_client.ping():
            checks["redis"] = "connected"
        else:
            checks["redis"] = "ping_failed"
            healthy = False
    except Exception as e:
        checks["redis"] = f"unreachable ({e.__class__.__name__})"
        healthy = False

    # 3. Local Embedding & Whisper Model check
    try:
        service = LocalMLService.get_instance()
        ml_health = service.health_check()
        checks["embeddings"] = ml_health["embeddings"]
        checks["whisper"] = ml_health["whisper"]
        if not service.is_ready:
            healthy = False
    except Exception as e:
        checks["embeddings"] = f"error ({e.__class__.__name__})"
        checks["whisper"] = f"error ({e.__class__.__name__})"
        healthy = False

    status_code = status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if healthy else "degraded",
            "components": checks,
        },
    )


# ==============================================================================
# Mock Session Endpoints (Walking Skeleton)
# ==============================================================================

@app.post("/api/v1/sessions/mock", response_model=MockSessionResponse)
async def create_mock_session(payload: MockSessionRequest) -> MockSessionResponse:
    """Spawns an interactive mock learning session routed via LangGraph state machine.

    Persists initial SessionState in Redis under `session:{session_id}` with a 24-hour TTL.
    """
    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    active_concept_id = "concept_recursion_core"

    concept_graph = [
        ConceptNodeState(
            concept_id="concept_call_stack_frames",
            title="Memory Architecture & Call Stacks",
            prerequisites=[],
            mastery_rating=min(1.0, payload.initial_rating + 0.1),
            status="MASTERED" if payload.initial_rating >= 0.75 else "ACTIVE",
            attempts=1,
        ),
        ConceptNodeState(
            concept_id=active_concept_id,
            title=payload.topic_title,
            prerequisites=["concept_call_stack_frames"],
            mastery_rating=payload.initial_rating,
            status="ACTIVE",
            attempts=0,
        ),
        ConceptNodeState(
            concept_id="concept_tail_recursion_opt",
            title="Tail Call Optimization & Complexity",
            prerequisites=[active_concept_id],
            mastery_rating=0.0,
            status="LOCKED",
            attempts=0,
        ),
    ]

    initial_session = SessionState(
        session_id=session_id,
        student_id=payload.student_id,
        mode="AI_GUIDED",
        domain=payload.domain,
        resource_scope="STRICT_UPLOAD_ONLY",
        topic_title=payload.topic_title,
        concept_graph=concept_graph,
        active_concept_id=active_concept_id,
        domain_strategy_weights={
            "visual": 1.2,
            "analogy": 1.4,
            "faded_example": 1.1,
            "socratic": 0.9,
            "protege": 1.0,
        },
        current_hint_level=0,
        detected_misconceptions=[],
        last_technique_used="INITIAL_DIAGNOSTIC",
    )

    # Execute LangGraph starter pipeline to decide pedagogical UI payload
    updated_session, action_payload = execute_turn(initial_session)

    # Persist in Redis with 24-hour TTL
    redis_key = f"session:{session_id}"
    try:
        redis_client.setex(
            redis_key,
            86400,
            updated_session.model_dump_json(),
        )
        logger.info("Persisted session %s to Redis with TTL=86400s", redis_key)
    except Exception as e:
        logger.error("Failed to persist session to Redis: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Redis persistence failure: {e}",
        )

    return MockSessionResponse(
        session=updated_session,
        action=action_payload,
    )


@app.get("/api/v1/sessions/{session_id}", response_model=SessionState)
async def get_session_state(session_id: str) -> SessionState:
    """Retrieves live SessionState directly from Redis cache."""
    redis_key = f"session:{session_id}"
    try:
        data = redis_client.get(redis_key)
        if not data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session with id '{session_id}' not found in cache.",
            )
        return SessionState.model_validate_json(data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error reading session from Redis: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cache read error: {e}",
        )


# ==============================================================================
# Voice Prosody Endpoint
# ==============================================================================

@app.post("/api/v1/voice/analyze")
async def analyze_voice(
    file: UploadFile = File(..., description="Audio file of student voice response (wav/mp3/m4a/webm)"),
) -> Dict[str, Any]:
    """Transcribes student voice audio and extracts speech rate, hesitation, and prosody metrics in English."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a filename.",
        )

    ext = os.path.splitext(file.filename)[1] or ".wav"
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        temp_path = tmp.name
        try:
            shutil.copyfileobj(file.file, tmp)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save uploaded audio: {e}",
            )

    try:
        local_service = LocalMLService.get_instance()
        metrics = local_service.analyze_voice(temp_path, language="en")
        return metrics
    except Exception as e:
        logger.error("Audio analysis failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Voice prosody analysis failed: {str(e)}",
        )
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
