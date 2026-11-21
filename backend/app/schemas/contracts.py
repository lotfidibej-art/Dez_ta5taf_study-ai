from typing import Annotated, Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field


# ==============================================================================
# 1. Concept & Session State Models
# ==============================================================================

class ConceptNodeState(BaseModel):
    """Represents a node within the subject knowledge dependency graph."""
    concept_id: str = Field(..., description="Unique slug or identifier for the concept.")
    title: str = Field(..., description="Human-readable concept title.")
    prerequisites: List[str] = Field(
        default_factory=list,
        description="List of parent concept_ids required before unlocking.",
    )
    mastery_rating: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Live estimated comprehension score between 0.0 and 1.0.",
    )
    status: Literal["LOCKED", "ACTIVE", "MASTERED"] = Field(
        default="LOCKED",
        description="Lifecycle status within current learning path.",
    )
    attempts: int = Field(
        default=0,
        ge=0,
        description="Number of interaction turns completed on this concept.",
    )
    summary_hook: Optional[str] = Field(
        default=None,
        description="Concise 1-2 sentence core mental model hook.",
    )


class SessionState(BaseModel):
    """Canonical session snapshot persisted in Redis and passed across LangGraph nodes."""
    session_id: str = Field(..., description="Unique UUID for this study session.")
    student_id: str = Field(..., description="Student identifier.")
    mode: Literal["AI_GUIDED", "SELF_GUIDED"] = Field(
        default="AI_GUIDED",
        description="Learning mode controlling tutor autonomy.",
    )
    domain: str = Field(
        default="computer_science",
        description="Academic field (e.g., computer_science, biology, mathematics).",
    )
    resource_scope: Literal["STRICT_UPLOAD_ONLY", "ENRICHED_EXTERNAL"] = Field(
        default="STRICT_UPLOAD_ONLY",
        description="Constraint boundary for RAG explanations and examples.",
    )
    topic_title: str = Field(..., description="Primary topic of this session.")
    concept_graph: List[ConceptNodeState] = Field(
        default_factory=list,
        description="Ordered or DAG list of concepts comprising the session syllabus.",
    )
    active_concept_id: str = Field(..., description="Currently focused concept_id.")
    domain_strategy_weights: Dict[str, float] = Field(
        default_factory=lambda: {
            "visual": 1.0,
            "analogy": 1.0,
            "faded_example": 1.0,
            "socratic": 1.0,
            "protege": 1.0,
        },
        description="Multi-armed bandit pedagogical technique weights.",
    )
    current_hint_level: Literal[0, 1, 2, 3] = Field(
        default=0,
        description="Contingent hint ladder depth (0 = no hint, 3 = high guidance).",
    )
    detected_misconceptions: List[str] = Field(
        default_factory=list,
        description="Accumulated active misconceptions flagged during turns.",
    )
    mastered_anchor_concepts: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Cross-domain mastered concepts available for analogy bridges.",
    )
    last_technique_used: str = Field(
        default="INITIAL_DIAGNOSTIC",
        description="Identifier of the most recent pedagogical technique rendered.",
    )


# ==============================================================================
# 2. Discriminated UI Action Payloads
# ==============================================================================

class FoundationBoardPayload(BaseModel):
    """Action payload rendered when conceptMastery < 0.40."""
    ui_component: Literal["FOUNDATION_BOARD"] = Field(
        default="FOUNDATION_BOARD",
        description="Discriminated union selector for UI component routing.",
    )
    concept_id: str = Field(..., description="Concept under explanation.")
    bullet_breakdown: List[str] = Field(
        ...,
        description="Concise, high-clarity bullet points defining the core mental model.",
    )
    mermaid_diagram: Optional[str] = Field(
        default=None,
        description="Valid Mermaid.js graph diagram text visualizing the structure.",
    )
    bridge_analogy: Optional[Dict[str, str]] = Field(
        default=None,
        description="Cross-domain analogy mapping (e.g. {'source': 'Stack of plates', 'target': 'Call stack'}).",
    )
    interactive_lab: Optional[Dict[str, str]] = Field(
        default=None,
        description="Interactive sandbox URL and instructions (e.g. PhET, Desmos, CodeSandbox).",
    )
    study_habit_nudge: Optional[str] = Field(
        default=None,
        description="Metacognitive coaching tip (e.g., 'Try drawing the call tree before coding').",
    )


class FadedWorkspacePayload(BaseModel):
    """Action payload rendered when 0.40 <= conceptMastery <= 0.75."""
    ui_component: Literal["FADED_EXAMPLE_WORKSPACE"] = Field(
        default="FADED_EXAMPLE_WORKSPACE",
        description="Discriminated union selector for UI component routing.",
    )
    problem_statement: str = Field(..., description="Challenge prompt or code objective.")
    steps: List[Dict[str, Any]] = Field(
        ...,
        description="Step sequence with completed worked steps followed by blank faded steps.",
    )
    active_hint: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Current hint tier guidance matching current_hint_level.",
    )


class MisconceptionTrapPayload(BaseModel):
    """Action payload rendered when conceptMastery > 0.75 (Adversarial Challenge)."""
    ui_component: Literal["MISCONCEPTION_TRAP"] = Field(
        default="MISCONCEPTION_TRAP",
        description="Discriminated union selector for UI component routing.",
    )
    scenario_intro: str = Field(
        ...,
        description="Prompt framing the subtle bug or conceptual fallacy to uncover.",
    )
    flawed_artifact: str = Field(
        ...,
        description="Code, math proof, or explanation containing an intentional subtle error.",
    )
    artifact_language: str = Field(
        default="python",
        description="Language or syntax of flawed_artifact (python, markdown, math).",
    )
    hidden_flaw_tag: str = Field(
        ...,
        description="Internal ground-truth flaw category used for automated grading.",
    )


class ProtegeStagePayload(BaseModel):
    """Action payload rendered when conceptMastery > 0.75 (Protégé Teaching Mode)."""
    ui_component: Literal["PROTEGE_VOICE_STAGE"] = Field(
        default="PROTEGE_VOICE_STAGE",
        description="Discriminated union selector for UI component routing.",
    )
    ai_persona_question: str = Field(
        ...,
        description="Question asked by the AI student requiring human explanation.",
    )
    target_explanation_points: List[str] = Field(
        ...,
        description="Key points student must vocalize to demonstrate causal understanding.",
    )
    require_voice_input: bool = Field(
        default=True,
        description="Flags frontend to record speech and extract prosody metrics.",
    )


# Canonical Discriminated Union for Frontend UI routing
AgentActionPayload = Annotated[
    Union[
        FoundationBoardPayload,
        FadedWorkspacePayload,
        MisconceptionTrapPayload,
        ProtegeStagePayload,
    ],
    Field(discriminator="ui_component"),
]


# ==============================================================================
# 3. Evaluation & Post-Session Artifacts
# ==============================================================================

class CognitiveSignals(BaseModel):
    """Multi-modal prosody and hesitation features extracted during response."""
    response_latency_sec: float = Field(..., description="Time taken to begin speaking/answering.")
    speech_rate_wpm: float = Field(..., description="Estimated words per minute.")
    filler_word_ratio: float = Field(..., description="Proportion of filler words (um, uh, like).")
    monotone_recitation_flag: bool = Field(
        ...,
        description="Flags rapid mechanical recall without authentic reasoning.",
    )
    self_correction_count: int = Field(
        default=0,
        description="Detected verbal mid-sentence revisions ('no wait, because...').",
    )


class TurnEvaluation(BaseModel):
    """Pedagogical evaluation emitted by Agent 3 on each student interaction turn."""
    cognitive_signals: CognitiveSignals
    factual_accuracy: float = Field(
        ..., ge=0.0, le=1.0, description="Surface truth value of the answer."
    )
    causal_depth_score: float = Field(
        ..., ge=0.0, le=1.0, description="Depth of causal understanding beyond rote recall."
    )
    previous_rating: float = Field(..., ge=0.0, le=1.0)
    updated_comprehension_rating: float = Field(..., ge=0.0, le=1.0)
    technique_reward_delta: float = Field(
        ..., description="Reward signal passed to bandit weights."
    )
    new_misconception_identified: Optional[str] = Field(
        default=None,
        description="Specific fallacy diagnosed during this turn.",
    )


class SessionResumeArtifact(BaseModel):
    """Permanent post-session scannable summary card."""
    session_id: str
    student_id: str
    domain: str
    core_mental_model: str = Field(
        ..., description="3-sentence synthesis of how the concept works."
    )
    winning_analogies: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Analogies that triggered high comprehension jumps.",
    )
    misconceptions_conquered: List[str] = Field(
        default_factory=list,
        description="Traps student successfully resolved.",
    )
    final_mastery_ratings: Dict[str, float] = Field(
        default_factory=dict,
        description="Ending score per concept node.",
    )
    recommended_refresher_date: str = Field(
        ..., description="Spaced repetition next review target."
    )


# ==============================================================================
# 4. Request / Response Contracts for Mock Endpoints
# ==============================================================================

class MockSessionRequest(BaseModel):
    """Payload to trigger the starter LangGraph walking skeleton."""
    student_id: str = Field(default="student_dev_01", description="Student ID.")
    domain: str = Field(default="computer_science", description="Academic field.")
    topic_title: str = Field(default="Recursion & Call Stacks", description="Topic to explore.")
    initial_rating: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description="Seed comprehension rating (e.g. 0.25 for Foundation, 0.55 for Practice, 0.85 for Mastery).",
    )


class MockSessionResponse(BaseModel):
    """Response containing initialized SessionState and selected AgentActionPayload."""
    session: SessionState
    action: AgentActionPayload


# ==============================================================================
# 5. Multimodal Ingestion & Baseline Diagnostic Models (Slice 2)
# ==============================================================================

class ResourceChunk(BaseModel):
    chunk_id: str
    session_id: str
    student_id: str
    concept_id: Optional[str] = None
    content: str
    source_name: str
    source_location: str


class DiagnosticQuestion(BaseModel):
    question_id: str = Field(..., description="Unique question identifier.")
    concept_id: str = Field(..., description="Target DAG concept identifier.")
    concept_title: str = Field(..., description="Target concept title.")
    question_text: str = Field(..., description="Open-ended question testing causal understanding.")
    depth_tier: Literal["FOUNDATIONAL", "INTERMEDIATE", "ADVANCED"] = Field(
        ..., description="Topological layer depth."
    )


class DiagnosticAnswer(BaseModel):
    question_id: str = Field(..., description="Matched question identifier.")
    concept_id: str = Field(..., description="Target concept identifier.")
    answer_text: str = Field(..., description="Student's typed or transcribed answer.")


class DiagnosticSubmission(BaseModel):
    answers: List[DiagnosticAnswer] = Field(..., description="Answers to the 3 diagnostic questions.")


class SessionInitResponse(BaseModel):
    session: SessionState
    diagnostic_questions: List[DiagnosticQuestion]
    extracted_chunk_count: int = Field(default=0, description="Number of source chunks ingested.")


class DiagnosticEvaluationItem(BaseModel):
    question_id: str
    concept_id: str
    factual_accuracy: float = Field(..., ge=0.0, le=1.0)
    causal_depth: float = Field(..., ge=0.0, le=1.0)
    feedback: str
    identified_misconception: Optional[str] = None


class DiagnosticEvaluationResponse(BaseModel):
    session: SessionState
    evaluations: List[DiagnosticEvaluationItem]
    action: AgentActionPayload
    overall_initial_rating: float
    summary: str


# ==============================================================================
# 6. Slice 3 Foundation Tier Contracts
# ==============================================================================

class UnderstandingCheckRequest(BaseModel):
    student_response: str = Field(..., description="Student's explanation or lab observation.")
    concept_id: Optional[str] = Field(None, description="Optional target concept ID; defaults to active_concept_id.")


class UnderstandingCheckResponse(BaseModel):
    session: SessionState
    action: AgentActionPayload
    factual_accuracy: float = Field(..., ge=0.0, le=1.0)
    causal_depth: float = Field(..., ge=0.0, le=1.0)
    updated_mastery_rating: float = Field(..., ge=0.0, le=1.0)
    feedback: str
    identified_misconception: Optional[str] = None
    advanced_tier: bool = Field(..., description="True if student advanced out of Foundation tier (<0.40).")


