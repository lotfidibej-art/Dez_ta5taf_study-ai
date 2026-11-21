import json
import logging
import os
import shutil
import tempfile
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import redis
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.orchestrator.graph import execute_turn
from app.orchestrator.graph_utils import get_one_hop_slice
from app.schemas.contracts import (
    ConceptNodeState,
    DiagnosticAnswer,
    DiagnosticEvaluationResponse,
    DiagnosticQuestion,
    DiagnosticSubmission,
    MockSessionRequest,
    MockSessionResponse,
    SessionInitResponse,
    SessionState,
    UnderstandingCheckRequest,
    UnderstandingCheckResponse,
)
from app.services.local_models import LocalMLService
from app.db.migrations import get_db_connection, run_migrations
from app.services.ingestion import ingest_and_embed_resources
from app.agents.ingestion_agent import extract_concept_dag
from app.agents.domain_profiler import hydrate_learner_profile
from app.agents.diagnostic_agent import generate_baseline_diagnostic
from app.agents.evaluator_agent import evaluate_diagnostic_submission

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
    """Lifecycle manager: run DB migrations and warm up local ML models during startup."""
    logger.info("Executing database startup migrations...")
    try:
        run_migrations()
        logger.info("Database migrations complete.")
    except Exception as e:
        logger.error("Error executing database migrations on startup: %s", e)

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
# Slice 2: Multimodal Ingestion, Concept DAG & Diagnostic Endpoints
# ==============================================================================

@app.post("/api/v1/sessions/init", response_model=SessionInitResponse)
async def initialize_session(
    student_id: str = Form("student_dev_01", description="Student identifier"),
    domain: str = Form("computer_science", description="Academic field"),
    topic_title: str = Form(..., description="Primary topic to study"),
    mode: str = Form("AI_GUIDED", description="Learning mode: AI_GUIDED or SELF_GUIDED"),
    resource_scope: str = Form("STRICT_UPLOAD_ONLY", description="STRICT_UPLOAD_ONLY or ENRICHED_EXTERNAL"),
    urls: Optional[str] = Form(None, description="Comma or newline-separated URLs (web articles, YouTube)"),
    files: Optional[List[UploadFile]] = File(None, description="Uploaded PDF/text resources"),
) -> SessionInitResponse:
    """Initializes a full study session (Slice 2).

    1. Ingests multimodal resources (PDFs, YouTube, Web), chunking & embedding into PostgreSQL.
    2. Runs Agent 1 (Concept Extractor) to generate a topological NetworkX DAG.
    3. Runs Agent 2 (Domain Profiler) to load technique weights and cross-domain anchor concepts.
    4. Runs Diagnostic Agent to generate 3 open-ended baseline questions.
    5. Caches SessionState in Redis with 24h TTL.
    """
    session_id = f"sess_{uuid.uuid4().hex[:12]}"

    # Process URLs
    url_list: List[str] = []
    if urls:
        clean_urls = urls.strip()
        if clean_urls.startswith("["):
            try:
                parsed = json.loads(clean_urls)
                if isinstance(parsed, list):
                    url_list.extend([str(u).strip() for u in parsed if str(u).strip()])
            except Exception:
                pass
        if not url_list:
            import re
            for line in re.split(r"[\n,]+", clean_urls):
                c = line.strip()
                if c:
                    url_list.append(c)

    # Process Uploaded Files
    file_tuples = []
    if files:
        for f in files:
            if f.filename:
                content = await f.read()
                file_tuples.append((f.filename, content))

    logger.info(
        "Initializing session %s for student=%s, topic='%s' with %d files, %d urls",
        session_id,
        student_id,
        topic_title,
        len(file_tuples),
        len(url_list),
    )

    # 1. Ingestion & Embedding
    chunks = ingest_and_embed_resources(
        session_id=session_id,
        student_id=student_id,
        files=file_tuples,
        urls=url_list,
    )

    # 2. Agent 1: Concept DAG Extraction & NetworkX validation
    raw_graph = extract_concept_dag(
        session_id=session_id,
        topic_title=topic_title,
        domain=domain,
        chunks=chunks,
    )

    # 3. Agent 2: Domain Profiler & Cross-Domain Memory
    strategy_weights, concept_graph, anchor_concepts = hydrate_learner_profile(
        student_id=student_id,
        domain=domain,
        concept_graph=raw_graph,
    )

    active_id = concept_graph[0].concept_id if concept_graph else "concept_core"

    session_state = SessionState(
        session_id=session_id,
        student_id=student_id,
        mode=mode,  # type: ignore
        domain=domain,
        resource_scope=resource_scope,  # type: ignore
        topic_title=topic_title,
        concept_graph=concept_graph,
        active_concept_id=active_id,
        domain_strategy_weights=strategy_weights,
        current_hint_level=0,
        detected_misconceptions=[],
        mastered_anchor_concepts=anchor_concepts,
        last_technique_used="INITIAL_ONBOARDING",
    )

    # 4. Diagnostic Agent: Generate 3 open-ended diagnostic questions across DAG tiers
    diagnostic_questions = generate_baseline_diagnostic(
        topic_title=topic_title,
        domain=domain,
        concept_graph=concept_graph,
    )

    # 5. Persist in Redis
    try:
        redis_client.setex(
            f"session:{session_id}",
            86400,
            session_state.model_dump_json(),
        )
        diag_json = json.dumps([q.model_dump() for q in diagnostic_questions])
        redis_client.setex(
            f"diagnostic:{session_id}",
            86400,
            diag_json,
        )
        logger.info("Session %s successfully initialized and cached in Redis.", session_id)
    except Exception as e:
        logger.error("Failed to persist session to Redis: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Redis persistence failure: {e}",
        )

    return SessionInitResponse(
        session=session_state,
        diagnostic_questions=diagnostic_questions,
        extracted_chunk_count=len(chunks),
    )


@app.post("/api/v1/sessions/{session_id}/diagnostic", response_model=DiagnosticEvaluationResponse)
async def submit_diagnostic_answers(
    session_id: str,
    payload: DiagnosticSubmission,
) -> DiagnosticEvaluationResponse:
    """Evaluates the student's 3 diagnostic answers (Agent 3) and enters the adaptive loop."""
    redis_key = f"session:{session_id}"
    session_data = redis_client.get(redis_key)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with id '{session_id}' not found.",
        )
    session = SessionState.model_validate_json(session_data)

    # Load diagnostic questions
    diag_data = redis_client.get(f"diagnostic:{session_id}")
    questions: List[DiagnosticQuestion] = []
    if diag_data:
        try:
            questions = [DiagnosticQuestion.model_validate(q) for q in json.loads(diag_data)]
        except Exception as e:
            logger.warning("Could not parse cached diagnostic questions: %s", e)

    # Evaluate using Agent 3
    eval_response = evaluate_diagnostic_submission(
        session=session,
        questions=questions,
        answers=payload.answers,
    )

    # Persist updated session
    try:
        redis_client.setex(
            redis_key,
            86400,
            eval_response.session.model_dump_json(),
        )
        logger.info("Session %s updated in Redis after diagnostic evaluation.", session_id)
    except Exception as e:
        logger.error("Redis persistence failure on diagnostic update: %s", e)

    return eval_response


@app.get("/api/v1/sessions/{session_id}/slice")
async def get_session_context_slice(session_id: str) -> Dict[str, Any]:
    """Inspects the deterministic 1-hop context slice provided to downstream pedagogical agents."""
    redis_key = f"session:{session_id}"
    session_data = redis_client.get(redis_key)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with id '{session_id}' not found.",
        )
    session = SessionState.model_validate_json(session_data)
    return get_one_hop_slice(session)


# ==============================================================================
# Slice 3: Foundation Understanding Check
# ==============================================================================

@app.post(
    "/api/v1/sessions/{session_id}/check-understanding",
    response_model=UnderstandingCheckResponse,
)
async def check_understanding(
    session_id: str,
    payload: UnderstandingCheckRequest,
) -> UnderstandingCheckResponse:
    """Evaluates student's 'explain it back in your own words' response on the Foundation Board.

    1. Retrieves SessionState from Redis.
    2. Evaluates student response via Agent 3 (Evaluator Agent).
    3. Fuses factual accuracy & causal depth to calculate updated mastery rating.
    4. Logs event to telemetry_events in PostgreSQL.
    5. Re-runs LangGraph orchestrator state machine to transition UI tier or advance concept.
    6. Persists updated session to Redis.
    """
    redis_key = f"session:{session_id}"
    session_data = redis_client.get(redis_key)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with id '{session_id}' not found in cache.",
        )

    session = SessionState.model_validate_json(session_data)
    target_concept_id = payload.concept_id or session.active_concept_id

    # Find the concept title
    concept_title = session.topic_title
    for node in session.concept_graph:
        if node.concept_id == target_concept_id:
            concept_title = node.title
            break

    # Build synthetic question for Agent 3 evaluation
    question = DiagnosticQuestion(
        question_id=f"check_{target_concept_id}",
        concept_id=target_concept_id,
        concept_title=concept_title,
        question_text=f"Explain in your own words how {concept_title} functions and what you observed.",
        depth_tier="FOUNDATIONAL",
    )
    answer = DiagnosticAnswer(
        question_id=question.question_id,
        concept_id=target_concept_id,
        answer_text=payload.student_response,
    )

    # Evaluate via Agent 3
    eval_resp = evaluate_diagnostic_submission(
        session=session,
        questions=[question],
        answers=[answer],
    )

    eval_item = eval_resp.evaluations[0] if eval_resp.evaluations else None
    factual_acc = eval_item.factual_accuracy if eval_item else 0.5
    causal_depth = eval_item.causal_depth if eval_item else 0.5
    feedback = eval_item.feedback if eval_item else "Good effort. Reviewing next steps."
    misconception = eval_item.identified_misconception if eval_item else None

    # Calculate updated node mastery: 60% factual + 40% causal
    fused_rating = round((0.6 * factual_acc) + (0.4 * causal_depth), 2)

    # Update active node in session
    for node in eval_resp.session.concept_graph:
        if node.concept_id == target_concept_id:
            node.mastery_rating = fused_rating
            if fused_rating >= 0.75:
                node.status = "MASTERED"
            else:
                node.status = "ACTIVE"
            break

    # Re-run LangGraph router to select next pedagogical tier action payload
    updated_session, next_action = execute_turn(eval_resp.session)

    # Check if student advanced out of Foundation tier (<0.40)
    advanced_tier = fused_rating >= 0.40

    # Log telemetry event to PostgreSQL
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO telemetry_events (session_id, student_id, event_type, payload)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        session_id,
                        session.student_id,
                        "FOUNDATION_UNDERSTANDING_CHECK",
                        json.dumps({
                            "concept_id": target_concept_id,
                            "factual_accuracy": factual_acc,
                            "causal_depth": causal_depth,
                            "updated_mastery_rating": fused_rating,
                            "advanced_tier": advanced_tier,
                            "identified_misconception": misconception,
                        }),
                    ),
                )
        logger.info("Logged telemetry event for session %s, concept %s", session_id, target_concept_id)
    except Exception as e:
        logger.warning("Could not log telemetry event to DB: %s", e)

    # Persist updated session in Redis
    try:
        redis_client.setex(
            redis_key,
            86400,
            updated_session.model_dump_json(),
        )
    except Exception as e:
        logger.error("Failed to update session in Redis: %s", e)

    return UnderstandingCheckResponse(
        session=updated_session,
        action=next_action,
        factual_accuracy=factual_acc,
        causal_depth=causal_depth,
        updated_mastery_rating=fused_rating,
        feedback=feedback,
        identified_misconception=misconception,
        advanced_tier=advanced_tier,
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
