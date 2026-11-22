import json
import logging
import os
import shutil
import tempfile
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import redis
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.orchestrator.graph import execute_turn
from app.orchestrator.graph_utils import get_one_hop_slice
from app.schemas.contracts import (
    ConceptNodeState,
    ContingentHint,
    DiagnosticAnswer,
    DiagnosticEvaluationResponse,
    DiagnosticQuestion,
    DiagnosticSubmission,
    HintResponse,
    MockSessionRequest,
    MockSessionResponse,
    ResourceChunk,
    SelfGuidedInjectRequest,
    SelfGuidedInjectResponse,
    SessionInitResponse,
    SessionState,
    SubmitTurnRequest,
    SubmitTurnResponse,
    UnderstandingCheckRequest,
    UnderstandingCheckResponse,
    VoiceProsodySignals,
    MiniExamPayload,
    ExamSubmitRequest,
    ExamResult,
    UpdateSessionModeRequest,
    SelectConceptRequest,
    SelectConceptResponse,
)
from app.services.bandit import update_bandit_weights
from app.services.local_models import LocalMLService
from app.db.migrations import get_db_connection, run_migrations
from app.services.ingestion import ingest_and_embed_resources
from app.agents.ingestion_agent import extract_concept_dag
from app.agents.domain_profiler import hydrate_learner_profile
from app.agents.diagnostic_agent import generate_baseline_diagnostic
from app.agents.evaluator_agent import evaluate_diagnostic_submission, evaluate_turn_submission
from app.agents.scaffolding_agent import generate_contingent_hint
from app.agents.exam_agent import generate_mini_exam, grade_mini_exam
from app.agents.resume_agent import synthesize_session_resume
from app.api.analytics import router as analytics_router

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

# Register Slice 7 Analytics API router
app.include_router(analytics_router)


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
    is_self_guided = payload.mode == "SELF_GUIDED"

    concept_graph = [
        ConceptNodeState(
            concept_id="concept_call_stack_frames",
            title="Memory Architecture & Call Stacks",
            prerequisites=[],
            mastery_rating=min(1.0, payload.initial_rating + 0.1),
            status="ACTIVE" if is_self_guided else ("MASTERED" if payload.initial_rating >= 0.75 else "ACTIVE"),
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
            status="ACTIVE" if is_self_guided else "LOCKED",
            attempts=0,
        ),
    ]

    initial_session = SessionState(
        session_id=session_id,
        student_id=payload.student_id,
        mode=payload.mode,
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
        redis_client.setex(
            f"action:{session_id}",
            86400,
            action_payload.model_dump_json(),
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
        redis_client.setex(
            f"action:{session_id}",
            86400,
            eval_response.action.model_dump_json(),
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
    request: Request,
) -> UnderstandingCheckResponse:
    """Evaluates student's 'explain it back in your own words' response on the Foundation Board.

    Supports both application/json and multipart/form-data with optional audio_file.
    1. Retrieves SessionState from Redis.
    2. Analyzes voice prosody if audio_file is provided.
    3. Evaluates student response via Agent 3.
    4. Enforces surface memorization guard & hesitation support.
    5. Updates multi-armed bandit weights and logs telemetry.
    6. Re-runs LangGraph state machine and persists to Redis.
    """
    redis_key = f"session:{session_id}"
    session_data = redis_client.get(redis_key)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with id '{session_id}' not found in cache.",
        )

    session = SessionState.model_validate_json(session_data)

    content_type = request.headers.get("content-type", "")
    student_response = ""
    target_concept_id = None
    prosody_signals = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        student_response = str(form.get("student_response") or "").strip()
        target_concept_id = form.get("concept_id")
        audio_file = form.get("audio_file")

        if audio_file and hasattr(audio_file, "filename") and audio_file.filename:
            ext = os.path.splitext(audio_file.filename)[1] or ".webm"
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                temp_path = tmp.name
                try:
                    shutil.copyfileobj(audio_file.file, tmp)
                    tmp.flush()
                    local_service = LocalMLService.get_instance()
                    prosody_signals = local_service.analyze_voice(temp_path, language="en")
                    if not student_response and prosody_signals.get("transcript"):
                        student_response = prosody_signals["transcript"]
                finally:
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                        except Exception:
                            pass
    else:
        body = await request.json()
        payload = UnderstandingCheckRequest.model_validate(body)
        student_response = payload.student_response
        target_concept_id = payload.concept_id

    target_concept_id = target_concept_id or session.active_concept_id

    # Find the concept title
    concept_title = session.topic_title
    prev_node_rating = 0.0
    for node in session.concept_graph:
        if node.concept_id == target_concept_id:
            concept_title = node.title
            prev_node_rating = node.mastery_rating
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
        answer_text=student_response,
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

    # Step 2 Prosody Anti-Memorization & Hesitation Rules
    if prosody_signals:
        if prosody_signals.get("hesitation_pause_count", 0) >= 2 or prosody_signals.get("filler_word_ratio", 0.0) > 0.12:
            if prosody_signals.get("self_correction_count", 0) > 0:
                causal_depth = min(1.0, round(causal_depth + 0.10, 2))
                feedback += " Good verbal self-correction noted as you explained the mechanics."
            else:
                feedback += " Take your time to articulate the causal mechanism before concluding."

    # Calculate updated node mastery: 60% factual + 40% causal
    fused_rating = round((0.6 * factual_acc) + (0.4 * causal_depth), 2)

    # Slice 6: Mistake Detection & Remediation in Foundation Check
    is_monotone = bool(prosody_signals and prosody_signals.get("monotone_recitation_flag", False))
    is_mistake = (factual_acc < 0.70) or (causal_depth < 0.65) or is_monotone

    # Surface memorization guard
    if is_monotone and factual_acc >= 0.80:
        fused_rating = min(fused_rating, 0.78)
        misconception = "Surface memorization detected: high-speed verbatim recall without causal elaboration"
        feedback = (
            "Surface memorization detected: your explanation was rapid and verbatim, but lacked causal synthesis. "
            "To achieve durable mastery, explain the underlying *why* and mechanisms in your own words."
        )

    remediation = None
    if is_mistake:
        # Cap rating to foundation tier (< 0.40) to prevent premature progression
        fused_rating = min(fused_rating, 0.38)
        advanced_tier = False

        from app.agents.remediation_agent import build_mistake_remediation
        cached_action = None
        action_data = redis_client.get(f"action:{session_id}")
        if action_data:
            try:
                cached_action = json.loads(action_data)
            except Exception:
                pass

        remediation = build_mistake_remediation(
            session_state=session,
            student_submission=student_response,
            identified_misconception=misconception,
            evaluation_feedback=feedback,
            active_action=cached_action,
        )
        consecutive_mistakes = remediation.consecutive_mistakes
    else:
        advanced_tier = fused_rating >= 0.40
        consecutive_mistakes = 0

    # Update active node in session
    for node in session.concept_graph:
        if node.concept_id == target_concept_id:
            node.mastery_rating = fused_rating
            if fused_rating >= 0.75:
                node.status = "MASTERED"
            elif fused_rating >= 0.40:
                node.status = "ACTIVE"
            break

    # Determine active_concept for next turn:
    active_id = target_concept_id
    if fused_rating >= 0.75 and not is_mistake:
        from app.orchestrator.graph_utils import get_next_unlocked_concept
        unlocked = get_next_unlocked_concept(session.concept_graph)
        if unlocked and unlocked != target_concept_id:
            active_id = unlocked

    # Multi-Armed Bandit update
    updated_weights = update_bandit_weights(
        student_id=session.student_id,
        domain=session.domain,
        last_technique_used="FOUNDATION_BOARD",
        previous_rating=prev_node_rating,
        updated_rating=fused_rating,
        current_weights=session.domain_strategy_weights,
    )

    current_session = session.model_copy(
        update={
            "concept_graph": session.concept_graph,
            "active_concept_id": active_id,
            "domain_strategy_weights": updated_weights,
            "last_technique_used": "FOUNDATION_BOARD",
            "consecutive_mistakes": consecutive_mistakes,
            "active_remediation": remediation,
        }
    )

    # Core Behavioral Rule: If mistake occurred, preserve the foundation board!
    if is_mistake and cached_action:
        from app.schemas.contracts import FoundationBoardPayload
        next_action = FoundationBoardPayload.model_validate(cached_action) if isinstance(cached_action, dict) and cached_action.get("ui_component") == "FOUNDATION_BOARD" else execute_turn(current_session)[1]
        updated_session = current_session
    else:
        updated_session, next_action = execute_turn(current_session)

    action_dict = next_action.model_dump() if hasattr(next_action, "model_dump") else cached_action
    updated_session = updated_session.model_copy(update={"last_action_payload": action_dict})

    # Log telemetry event to PostgreSQL
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                db_student_uuid = None
                try:
                    uuid.UUID(str(session.student_id))
                    db_student_uuid = str(session.student_id)
                except Exception:
                    cur.execute(
                        "SELECT id FROM students WHERE email = %s OR name = %s LIMIT 1",
                        (f"{session.student_id}@student.local", session.student_id),
                    )
                    s_row = cur.fetchone()
                    if s_row:
                        db_student_uuid = s_row[0]

                cur.execute(
                    """
                    INSERT INTO telemetry_events (session_id, student_id, event_type, payload)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        session_id,
                        db_student_uuid,
                        "FOUNDATION_UNDERSTANDING_CHECK",
                        json.dumps({
                            "concept_id": target_concept_id,
                            "factual_accuracy": factual_acc,
                            "causal_depth": causal_depth,
                            "updated_mastery_rating": fused_rating,
                            "advanced_tier": advanced_tier,
                            "identified_misconception": misconception,
                            "prosody_signals": prosody_signals,
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
        redis_client.setex(
            f"action:{session_id}",
            86400,
            next_action.model_dump_json(),
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
        prosody_signals=VoiceProsodySignals(**prosody_signals) if prosody_signals else None,
        remediation=remediation,
    )


# ==============================================================================
# Slice 4: Scaffolding Hints, Turn Submissions, and Self-Guided Exploration
# ==============================================================================

@app.post(
    "/api/v1/sessions/{session_id}/hint",
    response_model=HintResponse,
)
async def request_contingent_hint(session_id: str) -> HintResponse:
    """Delivers progressive scaffolding via the Contingent Hint Ladder (Levels 1 to 3).

    Level 1: Socratic conceptual nudge.
    Level 2: Strict source pointer quoting exact file & page/timestamp from resource_chunks.
    Level 3: Formula / code structural skeleton with blanks.
    """
    redis_key = f"session:{session_id}"
    session_data = redis_client.get(redis_key)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with id '{session_id}' not found.",
        )

    session = SessionState.model_validate_json(session_data)

    # Retrieve current workspace payload if cached
    from app.schemas.contracts import FadedWorkspacePayload
    action_data = redis_client.get(f"action:{session_id}")
    workspace = None
    if action_data:
        try:
            act_dict = json.loads(action_data)
            if act_dict.get("ui_component") == "FADED_EXAMPLE_WORKSPACE":
                workspace = FadedWorkspacePayload.model_validate(act_dict)
        except Exception:
            pass

    if not workspace:
        from app.agents.scaffolding_agent import _fallback_faded_workspace
        workspace = _fallback_faded_workspace(session, session.topic_title)

    # Generate next progressive hint level
    hint = generate_contingent_hint(session, workspace)

    # Increment hint level and persist
    new_hint_level = hint.level
    updated_session = session.model_copy(update={"current_hint_level": new_hint_level})

    # Attach hint to workspace and re-cache
    workspace.active_hint = hint.model_dump()
    redis_client.setex(redis_key, 86400, updated_session.model_dump_json())
    redis_client.setex(f"action:{session_id}", 86400, workspace.model_dump_json())

    return HintResponse(
        session=updated_session,
        active_hint=hint,
        hint_level=new_hint_level,
    )


@app.post(
    "/api/v1/sessions/{session_id}/submit-turn",
    response_model=SubmitTurnResponse,
)
async def submit_turn(
    session_id: str,
    request: Request,
) -> SubmitTurnResponse:
    """Unified turn evaluator for Faded Steps, Misconception Traps, and Protégé Challenges.

    Supports both application/json and multipart/form-data with optional audio_file.
    1. Retrieves SessionState and active action from Redis.
    2. Runs LocalMLService.analyze_voice() if an audio_file is attached.
    3. Grades response with Agent 3 (evaluator_agent), incorporating spoken prosody signals.
    4. Updates Multi-Armed Bandit weights in PostgreSQL and syncs to Redis.
    5. Advances concept or routes to next pedagogical tier via LangGraph.
    """
    redis_key = f"session:{session_id}"
    session_data = redis_client.get(redis_key)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with id '{session_id}' not found.",
        )

    session = SessionState.model_validate_json(session_data)

    content_type = request.headers.get("content-type", "")
    text_input = ""
    step_answers: Optional[Dict[str, str]] = None
    response_latency_sec = 0.0
    prosody_signals = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        text_input = str(form.get("text_input") or "").strip()
        step_answers_raw = form.get("step_answers")
        if step_answers_raw:
            try:
                if isinstance(step_answers_raw, str):
                    step_answers = json.loads(step_answers_raw)
                elif isinstance(step_answers_raw, dict):
                    step_answers = step_answers_raw
            except Exception:
                step_answers = None

        try:
            response_latency_sec = float(form.get("response_latency_sec") or 0.0)
        except Exception:
            response_latency_sec = 0.0

        audio_file = form.get("audio_file")
        if audio_file and hasattr(audio_file, "filename") and audio_file.filename:
            ext = os.path.splitext(audio_file.filename)[1] or ".webm"
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                temp_path = tmp.name
                try:
                    shutil.copyfileobj(audio_file.file, tmp)
                    tmp.flush()
                    local_service = LocalMLService.get_instance()
                    prosody_signals = local_service.analyze_voice(temp_path, language="en")
                    if not text_input and prosody_signals.get("transcript"):
                        text_input = prosody_signals["transcript"]
                finally:
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                        except Exception:
                            pass
    else:
        body = await request.json()
        payload = SubmitTurnRequest.model_validate(body)
        text_input = payload.text_input
        step_answers = payload.step_answers
        response_latency_sec = payload.response_latency_sec

    # Retrieve cached action payload
    action_data = redis_client.get(f"action:{session_id}")
    active_action = None
    if action_data:
        try:
            ad = json.loads(action_data)
            ui_c = ad.get("ui_component")
            if ui_c == "FADED_EXAMPLE_WORKSPACE":
                from app.schemas.contracts import FadedWorkspacePayload
                active_action = FadedWorkspacePayload.model_validate(ad)
            elif ui_c == "MISCONCEPTION_TRAP":
                from app.schemas.contracts import MisconceptionTrapPayload
                active_action = MisconceptionTrapPayload.model_validate(ad)
            elif ui_c == "PROTEGE_VOICE_STAGE":
                from app.schemas.contracts import ProtegeStagePayload
                active_action = ProtegeStagePayload.model_validate(ad)
        except Exception as e:
            logger.warning("Could not deserialize active action: %s", e)

    # Evaluate turn via Agent 3
    result: SubmitTurnResponse = evaluate_turn_submission(
        session=session,
        text_input=text_input,
        step_answers=step_answers,
        response_latency_sec=response_latency_sec,
        active_action=active_action,
        prosody_signals=prosody_signals,
    )

    # Update Redis cache
    redis_client.setex(redis_key, 86400, result.session.model_dump_json())
    redis_client.setex(f"action:{session_id}", 86400, result.action.model_dump_json())

    return result


@app.get(
    "/api/v1/sessions/{session_id}/chunks",
    response_model=List[ResourceChunk],
)
async def get_session_resource_chunks(session_id: str) -> List[ResourceChunk]:
    """Retrieves all ingested multimodal resource chunks with source citations for Self-Guided reading."""
    chunks: List[ResourceChunk] = []
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT chunk_id, session_id, student_id, concept_id, content, 
                           source_name, source_location, embedding
                    FROM resource_chunks 
                    WHERE session_id = %s
                    ORDER BY source_name ASC, chunk_id ASC
                    """,
                    (session_id,),
                )
                rows = cur.fetchall()
                for r in rows:
                    c_id, sess_id, st_id, conc_id, content, s_name, s_loc, emb = r
                    emb_list = None
                    if emb is not None:
                        if hasattr(emb, "to_list"):
                            emb_list = emb.to_list()
                        elif hasattr(emb, "tolist"):
                            emb_list = emb.tolist()
                        else:
                            emb_list = list(emb)
                    chunks.append(
                        ResourceChunk(
                            chunk_id=str(c_id),
                            session_id=str(sess_id),
                            student_id=str(st_id),
                            concept_id=conc_id,
                            content=content,
                            source_name=s_name,
                            source_location=s_loc,
                            embedding=emb_list,
                        )
                    )
    except Exception as e:
        logger.error("Failed to query resource_chunks for session %s: %s", session_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database retrieval error: {e}",
        )
    return chunks


@app.post(
    "/api/v1/sessions/{session_id}/self-guided/inject",
    response_model=SelfGuidedInjectResponse,
)
async def self_guided_inject(
    session_id: str,
    payload: SelfGuidedInjectRequest,
) -> SelfGuidedInjectResponse:
    """Maps highlighted text in Self-Guided mode to its closest concept node via pgvector,

    sets the calibrated initial rating (0.30 for EXPLAIN -> Foundation; 0.55 for QUIZ -> Scaffolding),
    and routes directly into the LangGraph state machine.
    """
    redis_key = f"session:{session_id}"
    session_data = redis_client.get(redis_key)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with id '{session_id}' not found.",
        )

    session = SessionState.model_validate_json(session_data)

    # 1. Embed selected text snippet
    ml_service = LocalMLService.get_instance()
    snippet_emb = ml_service.embed_text([payload.selected_text])
    vec = snippet_emb[0] if snippet_emb else [0.0] * 384

    # 2. Match to closest concept node in PostgreSQL pgvector or in session concept_graph
    matched_concept_id = session.active_concept_id
    matched_concept_title = session.topic_title

    try:
        import numpy as np
        # Compute similarities against session concept nodes
        concept_texts = [f"{n.title}. {n.summary_hook or ''}" for n in session.concept_graph]
        if concept_texts:
            concept_embs = np.array(ml_service.embed_text(concept_texts), dtype=np.float32)
            query_vec = np.array(vec, dtype=np.float32)
            sims = np.dot(concept_embs, query_vec)
            best_idx = int(np.argmax(sims))
            matched_concept_id = session.concept_graph[best_idx].concept_id
            matched_concept_title = session.concept_graph[best_idx].title
    except Exception as e:
        logger.warning("Could not match concept vector: %s", e)

    # 3. Calibrate mastery based on user intent
    assigned_rating = 0.30 if payload.intent == "EXPLAIN" else 0.55

    for node in session.concept_graph:
        if node.concept_id == matched_concept_id:
            node.mastery_rating = assigned_rating
            node.status = "ACTIVE"
            break

    updated_session_state = session.model_copy(
        update={
            "concept_graph": session.concept_graph,
            "active_concept_id": matched_concept_id,
            "current_hint_level": 0,
            "last_technique_used": f"SELF_GUIDED_{payload.intent}",
        }
    )

    # 4. Re-run LangGraph router
    final_session, next_action = execute_turn(updated_session_state)

    # Persist updated session and action in Redis
    redis_client.setex(redis_key, 86400, final_session.model_dump_json())
    redis_client.setex(f"action:{session_id}", 86400, next_action.model_dump_json())

    return SelfGuidedInjectResponse(
        session=final_session,
        action=next_action,
        concept_id=matched_concept_id,
        concept_title=matched_concept_title,
        assigned_mastery_rating=assigned_rating,
        intent=payload.intent,
    )


@app.patch("/api/v1/sessions/{session_id}/mode", response_model=SessionState)
async def update_session_mode(
    session_id: str,
    payload: UpdateSessionModeRequest,
) -> SessionState:
    """Toggles session learning mode between AI_GUIDED and SELF_GUIDED."""
    redis_key = f"session:{session_id}"
    session_data = redis_client.get(redis_key)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with id '{session_id}' not found.",
        )
    session = SessionState.model_validate_json(session_data)
    session.mode = payload.mode
    if payload.mode == "SELF_GUIDED":
        for node in session.concept_graph:
            if node.status == "LOCKED":
                node.status = "ACTIVE"
    redis_client.setex(redis_key, 86400, session.model_dump_json())
    logger.info("Session %s switched mode to %s", session_id, payload.mode)
    return session


@app.post(
    "/api/v1/sessions/{session_id}/select-concept",
    response_model=SelectConceptResponse,
)
async def select_concept(
    session_id: str,
    payload: SelectConceptRequest,
) -> SelectConceptResponse:
    """Allows student in self-guided mode to pick any concept and pedagogical activity type."""
    redis_key = f"session:{session_id}"
    session_data = redis_client.get(redis_key)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with id '{session_id}' not found.",
        )
    session = SessionState.model_validate_json(session_data)

    # 1. Update active concept
    session.active_concept_id = payload.concept_id

    # 2. Map target stage to calibrated mastery rating
    stage_rating_map = {
        "FOUNDATION": 0.25,
        "PRACTICE": 0.55,
        "CHALLENGE": 0.80,
        "PROTEGE": 0.88,
        "EXAM": 0.90,
    }
    target_rating = stage_rating_map.get(payload.target_stage, 0.35)
    for node in session.concept_graph:
        if node.concept_id == payload.concept_id:
            node.mastery_rating = target_rating
            node.status = "ACTIVE"
            break

    session.current_hint_level = 0
    session.active_remediation = None
    session.consecutive_mistakes = 0
    session.last_technique_used = f"SELF_GUIDED_{payload.target_stage}"

    # 3. If target is EXAM, generate mini-exam directly
    if payload.target_stage == "EXAM":
        exam = generate_mini_exam(session)
        redis_client.setex(redis_key, 86400, session.model_dump_json())
        return SelectConceptResponse(
            session=session,
            action=None,
            exam=exam,
        )

    # 4. Re-run LangGraph router to produce corresponding stage payload
    final_session, next_action = execute_turn(session)
    redis_client.setex(redis_key, 86400, final_session.model_dump_json())
    redis_client.setex(f"action:{session_id}", 86400, next_action.model_dump_json())

    return SelectConceptResponse(
        session=final_session,
        action=next_action,
        exam=None,
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


# ==============================================================================
# Slice 7: Adaptive Mini-Exams & Session Résumés
# ==============================================================================

@app.post(
    "/api/v1/sessions/{session_id}/mini-exam/start",
    response_model=MiniExamPayload,
)
async def start_mini_exam(session_id: str) -> MiniExamPayload:
    """Agent 8: Generates an adaptive 4-question mini-exam targeting session misconceptions (Slice 7)."""
    redis_key = f"session:{session_id}"
    session_data = redis_client.get(redis_key)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with id '{session_id}' not found.",
        )
    session = SessionState.model_validate_json(session_data)

    exam_payload = generate_mini_exam(session)

    # Cache exam payload in Redis for 86400 seconds
    redis_client.setex(
        f"exam:{session_id}",
        86400,
        exam_payload.model_dump_json(),
    )
    logger.info("Generated mini-exam %s for session %s", exam_payload.exam_id, session_id)
    return exam_payload


@app.post(
    "/api/v1/sessions/{session_id}/mini-exam/submit",
    response_model=ExamResult,
)
async def submit_mini_exam(
    session_id: str,
    payload: ExamSubmitRequest,
) -> ExamResult:
    """Grades mini-exam (Agent 8) and synthesizes permanent session résumé (Agent 9) (Slice 7)."""
    redis_key = f"session:{session_id}"
    session_data = redis_client.get(redis_key)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with id '{session_id}' not found.",
        )
    session = SessionState.model_validate_json(session_data)

    # Retrieve cached exam
    exam_data = redis_client.get(f"exam:{session_id}")
    if exam_data:
        exam = MiniExamPayload.model_validate_json(exam_data)
    else:
        # Fallback: re-generate exam if expired
        exam = generate_mini_exam(session)

    # 1. Grade exam via Agent 8
    submissions_list = [s.model_dump() for s in payload.submissions]
    exam_result = grade_mini_exam(session, exam, submissions_list)

    # 2. Synthesize session résumé & update spaced repetition via Agent 9
    try:
        resume_artifact = synthesize_session_resume(session, exam_result)
        exam_result.resume = resume_artifact
    except Exception as e:
        logger.error("Error synthesizing session résumé: %s", e, exc_info=True)

    # Cache result in Redis
    redis_client.setex(
        f"exam_result:{session_id}",
        86400,
        exam_result.model_dump_json(),
    )
    logger.info(
        "Graded mini-exam for session %s: score=%.2f, passed=%s",
        session_id,
        exam_result.exam_score,
        exam_result.passed,
    )
    return exam_result

