from __future__ import annotations

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
    protege_turn_count: int = Field(
        default=0,
        ge=0,
        description="Number of consecutive protégé teaching turns completed on the active concept.",
    )
    consecutive_mistakes: int = Field(
        default=0,
        ge=0,
        description="Sequential mistake count on the active concept.",
    )
    active_remediation: Optional[RemediationFeedback] = Field(
        default=None,
        description="Active mistake counter-example and progressive auto-hint.",
    )
    last_action_payload: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Caches the current problem/workspace in Redis so retries keep the exact same problem state.",
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
    concept_id: str = Field(default="", description="Concept under practice.")
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
    concept_id: str = Field(default="", description="Concept under challenge.")
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
    concept_id: str = Field(default="", description="Concept to teach.")
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
    follow_up_pushback: Optional[str] = Field(
        default=None,
        description="Targeted follow-up Socratic question when prior explanation missed core points.",
    )
    turn_number: int = Field(
        default=1,
        description="Dialogue turn index in the protégé interaction sequence.",
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


class ConqueredMisconceptionItem(BaseModel):
    false_belief: str
    corrected_truth: str
    concept_id: Optional[str] = None


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
    misconceptions_conquered: List[Union[Dict[str, str], ConqueredMisconceptionItem, str]] = Field(
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
    initial_mastery: float = Field(default=0.0)
    final_mastery: float = Field(default=0.0)
    mastery_velocity: float = Field(default=0.0, description="Mastery delta per minute.")
    duration_minutes: float = Field(default=0.0)
    most_effective_technique: Optional[str] = Field(default=None)
    exam_score: Optional[float] = Field(default=None)
    next_spaced_review_at: Optional[str] = Field(default=None)
    analytics: Dict[str, Any] = Field(default_factory=dict)
    due_for_review: bool = Field(default=False)


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
    mode: Literal["AI_GUIDED", "SELF_GUIDED"] = Field(
        default="AI_GUIDED",
        description="Learning mode: AI_GUIDED (system automated progression) or SELF_GUIDED (student freedom).",
    )


class MockSessionResponse(BaseModel):
    """Response containing initialized SessionState and selected AgentActionPayload."""
    session: SessionState
    action: AgentActionPayload


class UpdateSessionModeRequest(BaseModel):
    mode: Literal["AI_GUIDED", "SELF_GUIDED"] = Field(
        description="Target mode: AI_GUIDED (automated prerequisite routing) or SELF_GUIDED (student picks any lesson/test)."
    )


class SelectConceptRequest(BaseModel):
    concept_id: str = Field(description="The concept node to focus on.")
    target_stage: Literal["FOUNDATION", "PRACTICE", "CHALLENGE", "PROTEGE", "EXAM"] = Field(
        default="FOUNDATION",
        description="The desired pedagogical activity type."
    )


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


# ==============================================================================
# Slice 5 Voice Prosody Signals
# ==============================================================================

class VoiceProsodySignals(BaseModel):
    transcript: str = Field(default="", description="Transcribed student audio.")
    speech_rate_wpm: float = Field(default=0.0, description="Calculated words per minute.")
    hesitation_pause_count: int = Field(default=0, description="Inter-word pauses > 1.5s.")
    max_pause_sec: float = Field(default=0.0, description="Longest pause duration in seconds.")
    filler_word_ratio: float = Field(default=0.0, description="Ratio of filler words to total words.")
    self_correction_count: int = Field(default=0, description="Detected phrase restarts or self-corrections.")
    monotone_recitation_flag: bool = Field(default=False, description="Flag for high-speed unreflective recall.")
    fluency_signal: Optional[str] = Field(default=None, description="Qualitative speech fluency classification.")
    total_words: int = Field(default=0, description="Total word count in transcription.")


class UnderstandingCheckResponse(BaseModel):
    session: SessionState
    action: AgentActionPayload
    factual_accuracy: float = Field(..., ge=0.0, le=1.0)
    causal_depth: float = Field(..., ge=0.0, le=1.0)
    updated_mastery_rating: float = Field(..., ge=0.0, le=1.0)
    feedback: str
    identified_misconception: Optional[str] = None
    advanced_tier: bool = Field(..., description="True if student advanced out of Foundation tier (<0.40).")
    prosody_signals: Optional[VoiceProsodySignals] = Field(
        default=None,
        description="Prosody signals extracted if voice audio was submitted.",
    )
    remediation: Optional[RemediationFeedback] = Field(
        default=None,
        description="Mistake counter-example and progressive auto-hint if understanding check fell short.",
    )


# ==============================================================================
# 7. Slice 4 Scaffolding, Traps & Self-Guided Contracts
# ==============================================================================

class SourceCitation(BaseModel):
    file_name: str
    page_or_timestamp: str


class ContingentHint(BaseModel):
    level: int = Field(..., ge=1, le=3)
    hint_text: str
    hint_type: Literal["CONCEPTUAL_NUDGE", "SOURCE_POINTER", "STRUCTURAL_SKELETON"]
    source_citation: Optional[SourceCitation] = None
    skeleton_template: Optional[str] = None


class HintResponse(BaseModel):
    session: SessionState
    active_hint: ContingentHint
    hint_level: int


class SubmitTurnRequest(BaseModel):
    text_input: str = Field(..., description="Student's written explanation or overall answer.")
    step_answers: Optional[Dict[str, str]] = Field(
        default=None,
        description="Keyed responses for individual faded steps (e.g. {'3': 'n + sum_to_n(n-1)'}).",
    )
    response_latency_sec: float = Field(
        default=0.0,
        description="Time taken to submit the response in seconds.",
    )


class TurnEvaluationItem(BaseModel):
    factual_accuracy: float = Field(..., ge=0.0, le=1.0)
    causal_depth: float = Field(..., ge=0.0, le=1.0)
    feedback: str
    identified_misconception: Optional[str] = None
    hint_penalty_applied: float = Field(
        default=0.0,
        description="Penalty deducted from score based on hint level (-0.03 per hint level).",
    )
    prosody_signals: Optional[VoiceProsodySignals] = Field(
        default=None,
        description="Prosody signals extracted if turn was submitted via voice.",
    )


class SubmitTurnResponse(BaseModel):
    session: SessionState
    evaluation: TurnEvaluationItem
    action: AgentActionPayload
    updated_mastery_rating: float = Field(..., ge=0.0, le=1.0)
    concept_mastered: bool = Field(
        default=False,
        description="True if updated_mastery_rating >= 0.85 and concept advanced.",
    )
    remediation: Optional[RemediationFeedback] = Field(
        default=None,
        description="Active counter-example and progressive auto-hint attached when a mistake occurs.",
    )


# ==============================================================================
# 8. Slice 6 Mistake Remediation Contracts
# ==============================================================================

class CounterExample(BaseModel):
    title: str = Field(
        default="Counter-Example: When Your Rule Breaks",
        description="Attention-focusing title highlighting the specific edge condition.",
    )
    input_or_scenario: str = Field(
        ...,
        description="Concrete edge-case input, code trace, or domain counter-case.",
    )
    expected_vs_student_outcome: str = Field(
        ...,
        description="Contrasts what the student's assumption predicts vs. what actually occurs.",
    )


class AutoHint(BaseModel):
    level: Literal[1, 2, 3] = Field(
        ...,
        description="Progressive guidance level (1 = conceptual nudge, 2 = source pointer, 3 = structural skeleton).",
    )
    hint_text: str = Field(
        ...,
        description="Actionable clue pointing toward resolution without giving away the final answer.",
    )
    source_citation: Optional[SourceCitation] = Field(
        default=None,
        description="Exact file_name and page/timestamp on Level 2+.",
    )


class RemediationFeedback(BaseModel):
    is_mistake: bool = Field(default=True, description="True if student answer failed correctness/depth thresholds.")
    consecutive_mistakes: int = Field(default=1, description="Number of sequential mistakes on this concept.")
    diagnosis_summary: str = Field(
        ...,
        description="1-2 sentences explaining what went wrong in the student's reasoning.",
    )
    counter_example: CounterExample
    auto_hint: AutoHint
    should_backtrack_prerequisite: bool = Field(
        default=False,
        description="True if student has stalled across multiple attempts and needs prerequisite reinforcement.",
    )


class SelfGuidedInjectRequest(BaseModel):
    selected_text: str = Field(..., description="Highlighted text snippet from the document.")
    intent: Literal["EXPLAIN", "QUIZ"] = Field(
        ...,
        description="'EXPLAIN' maps to 0.30 mastery (Foundation); 'QUIZ' maps to 0.55 mastery (Scaffolding).",
    )


class SelfGuidedInjectResponse(BaseModel):
    session: SessionState
    action: AgentActionPayload
    concept_id: str
    concept_title: str
    assigned_mastery_rating: float
    intent: Literal["EXPLAIN", "QUIZ"]


# ==============================================================================
# 10. Adaptive Mini-Exam & Analytics Contracts (Slice 7)
# ==============================================================================

class MiniExamQuestion(BaseModel):
    question_id: str
    type: Literal["MCQ", "FADED_TRANSFER", "CAUSAL_SYNTHESIS"]
    prompt: str
    options: Optional[List[str]] = Field(
        default=None,
        description="Distractor and correct options for MCQs (targeted at misconceptions).",
    )
    faded_context: Optional[str] = Field(
        default=None,
        description="Partial scenario or code context for faded transfer problems.",
    )
    target_concept_id: str


class MiniExamPayload(BaseModel):
    exam_id: str
    session_id: str
    questions: List[MiniExamQuestion]
    hints_enabled: bool = False
    instructions: str = Field(
        default="Complete all 4 questions. Hints are disabled during this final check.",
        description="Instructions for the mini-exam.",
    )


class ExamAnswerSubmission(BaseModel):
    question_id: str
    answer: str


class ExamSubmitRequest(BaseModel):
    submissions: List[ExamAnswerSubmission]


class ExamGradedItem(BaseModel):
    question_id: str
    score: float = Field(..., ge=0.0, le=1.0)
    student_answer: str
    feedback: str
    lingering_flaw: Optional[str] = None


class ExamResult(BaseModel):
    exam_id: str
    session_id: str
    exam_score: float = Field(..., ge=0.0, le=1.0)
    passed: bool
    graded_questions: List[ExamGradedItem]
    lingering_weak_concepts: List[str] = Field(default_factory=list)
    resume: Optional[SessionResumeArtifact] = None


class SelectConceptResponse(BaseModel):
    session: SessionState
    action: Optional[AgentActionPayload] = None
    exam: Optional[MiniExamPayload] = None


class AnalyticsKPIs(BaseModel):
    global_mastery_avg: float
    mastery_delta_30d: float
    avg_mastery_velocity_per_min: float
    durable_retention_rate: float
    surface_memorization_drop_pct: float


class FieldMastery(BaseModel):
    domain: str
    mastery_score: float
    concepts_mastered: int
    concepts_in_progress: int
    best_technique: str


class TechniqueStat(BaseModel):
    technique: str
    avg_rating_gain: float
    usage_count: int


class MasterySpeedTimeseriesPoint(BaseModel):
    week: str
    cumulative_mastered: int
    avg_minutes_to_mastery: float


class LessonsLearnedVault(BaseModel):
    conquered_misconceptions: List[Dict[str, Any]] = Field(default_factory=list)
    recent_resumes: List[SessionResumeArtifact] = Field(default_factory=list)


class StudentAnalyticsDashboard(BaseModel):
    student_id: str
    kpis: AnalyticsKPIs
    mastery_per_field: List[FieldMastery]
    learning_style_effectiveness: Dict[str, List[TechniqueStat]]
    mastery_speed_timeseries: List[MasterySpeedTimeseriesPoint]
    lessons_learned_vault: LessonsLearnedVault



