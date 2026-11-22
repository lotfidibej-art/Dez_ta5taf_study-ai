import { components } from "@/types/api";

export type SessionState = components["schemas"]["SessionState"];
export type ConceptNodeState = components["schemas"]["ConceptNodeState"];
export type FoundationBoardPayload = components["schemas"]["FoundationBoardPayload"];
export type FadedWorkspacePayload = components["schemas"]["FadedWorkspacePayload"];
export type MisconceptionTrapPayload = components["schemas"]["MisconceptionTrapPayload"];
export type ProtegeStagePayload = components["schemas"]["ProtegeStagePayload"];

export type AgentActionPayload =
  | FoundationBoardPayload
  | FadedWorkspacePayload
  | MisconceptionTrapPayload
  | ProtegeStagePayload;

export type MockSessionRequest = components["schemas"]["MockSessionRequest"];
export type MockSessionResponse = components["schemas"]["MockSessionResponse"];

export type DiagnosticQuestion = components["schemas"]["DiagnosticQuestion"];
export type DiagnosticAnswer = components["schemas"]["DiagnosticAnswer"];
export type DiagnosticSubmission = components["schemas"]["DiagnosticSubmission"];
export type SessionInitResponse = components["schemas"]["SessionInitResponse"];
export type DiagnosticEvaluationItem = components["schemas"]["DiagnosticEvaluationItem"];
export type DiagnosticEvaluationResponse = components["schemas"]["DiagnosticEvaluationResponse"];
export type ResourceChunk = components["schemas"]["ResourceChunk"];
export type SourceCitation = components["schemas"]["SourceCitation"];
export type ContingentHint = components["schemas"]["ContingentHint"];
export type HintResponse = components["schemas"]["HintResponse"];
export interface SubmitTurnRequest {
  text_input: string;
  step_answers?: Record<string, string> | null;
  response_latency_sec?: number;
}
export type TurnEvaluationItem = components["schemas"]["TurnEvaluationItem"];
export type SubmitTurnResponse = components["schemas"]["SubmitTurnResponse"];
export type SelfGuidedInjectRequest = components["schemas"]["SelfGuidedInjectRequest"];
export type SelfGuidedInjectResponse = components["schemas"]["SelfGuidedInjectResponse"];
export type CounterExample = components["schemas"]["CounterExample"];
export type AutoHint = components["schemas"]["AutoHint"];
export type RemediationFeedback = components["schemas"]["RemediationFeedback"];
export type MiniExamQuestion = components["schemas"]["MiniExamQuestion"];
export type MiniExamPayload = components["schemas"]["MiniExamPayload"];
export type ExamAnswerSubmission = components["schemas"]["ExamAnswerSubmission"];
export type ExamSubmitRequest = components["schemas"]["ExamSubmitRequest"];
export type ExamGradedItem = components["schemas"]["ExamGradedItem"];
export type ExamResult = components["schemas"]["ExamResult"];
export type SessionResumeArtifact = components["schemas"]["SessionResumeArtifact"];
export type StudentAnalyticsDashboard = components["schemas"]["StudentAnalyticsDashboard"];
export type AnalyticsKPIs = components["schemas"]["AnalyticsKPIs"];
export type FieldMastery = components["schemas"]["FieldMastery"];
export type TechniqueStat = components["schemas"]["TechniqueStat"];
export type MasterySpeedTimeseriesPoint = components["schemas"]["MasterySpeedTimeseriesPoint"];
export type LessonsLearnedVault = components["schemas"]["LessonsLearnedVault"];

export interface VoiceProsodySignals {
  transcript: string;
  speech_rate_wpm: number;
  hesitation_pause_count: number;
  max_pause_sec: number;
  filler_word_ratio: number;
  self_correction_count: number;
  monotone_recitation_flag: boolean;
  fluency_signal?: string | null;
  total_words: number;
}

export interface UnderstandingCheckRequest {
  student_response: string;
  concept_id?: string | null;
}

export interface UnderstandingCheckResponse {
  session: SessionState;
  action: AgentActionPayload;
  factual_accuracy: number;
  causal_depth: number;
  updated_mastery_rating: number;
  feedback: string;
  identified_misconception?: string | null;
  advanced_tier: boolean;
  prosody_signals?: VoiceProsodySignals | null;
  remediation?: RemediationFeedback | null;
}

export interface HealthComponents {
  postgres?: string;
  vector_extension?: string;
  redis?: string;
  embeddings?: string;
  whisper?: string;
  [key: string]: string | undefined;
}

export interface HealthCheckResponse {
  status: string;
  components: HealthComponents;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function getHealthStatus(): Promise<HealthCheckResponse> {
  const res = await fetch(`${API_BASE}/health`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Health check failed with status: ${res.status}`);
  }
  return res.json();
}

export async function createMockSession(
  payload: MockSessionRequest
): Promise<MockSessionResponse> {
  const res = await fetch(`${API_BASE}/api/v1/sessions/mock`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errorBody = await res.text();
    throw new Error(`Failed to create session (${res.status}): ${errorBody}`);
  }
  return res.json();
}

export async function getSessionState(sessionId: string): Promise<SessionState> {
  const res = await fetch(`${API_BASE}/api/v1/sessions/${encodeURIComponent(sessionId)}`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch session (${res.status})`);
  }
  return res.json();
}

export async function initSession(formData: FormData): Promise<SessionInitResponse> {
  const res = await fetch(`${API_BASE}/api/v1/sessions/init`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const errorBody = await res.text();
    throw new Error(`Session initialization failed (${res.status}): ${errorBody}`);
  }
  return res.json();
}

export async function submitDiagnosticAnswers(
  sessionId: string,
  answers: DiagnosticAnswer[]
): Promise<DiagnosticEvaluationResponse> {
  const res = await fetch(`${API_BASE}/api/v1/sessions/${encodeURIComponent(sessionId)}/diagnostic`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ answers }),
  });
  if (!res.ok) {
    const errorBody = await res.text();
    throw new Error(`Diagnostic evaluation failed (${res.status}): ${errorBody}`);
  }
  return res.json();
}

export async function getSessionSlice(sessionId: string): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/api/v1/sessions/${encodeURIComponent(sessionId)}/slice`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch 1-hop context slice (${res.status})`);
  }
  return res.json();
}

export async function checkUnderstanding(
  sessionId: string,
  payload: UnderstandingCheckRequest | FormData
): Promise<UnderstandingCheckResponse> {
  const isFormData = typeof FormData !== "undefined" && payload instanceof FormData;
  const res = await fetch(
    `${API_BASE}/api/v1/sessions/${encodeURIComponent(sessionId)}/check-understanding`,
    {
      method: "POST",
      headers: isFormData ? undefined : { "Content-Type": "application/json" },
      body: isFormData ? payload : JSON.stringify(payload),
    }
  );
  if (!res.ok) {
    const errorBody = await res.text();
    throw new Error(`Understanding check failed (${res.status}): ${errorBody}`);
  }
  return res.json();
}

export async function checkUnderstandingVoice(
  sessionId: string,
  audioBlob: Blob,
  conceptId?: string | null
): Promise<UnderstandingCheckResponse> {
  const fd = new FormData();
  fd.append("audio_file", audioBlob, "reflection.webm");
  if (conceptId) {
    fd.append("concept_id", conceptId);
  }
  return checkUnderstanding(sessionId, fd);
}

export async function requestHint(sessionId: string): Promise<HintResponse> {
  const res = await fetch(`${API_BASE}/api/v1/sessions/${encodeURIComponent(sessionId)}/hint`, {
    method: "POST",
  });
  if (!res.ok) {
    const errorBody = await res.text();
    throw new Error(`Failed to request hint (${res.status}): ${errorBody}`);
  }
  return res.json();
}

export async function submitTurn(
  sessionId: string,
  payload: SubmitTurnRequest | FormData
): Promise<SubmitTurnResponse> {
  const isFormData = typeof FormData !== "undefined" && payload instanceof FormData;
  const res = await fetch(`${API_BASE}/api/v1/sessions/${encodeURIComponent(sessionId)}/submit-turn`, {
    method: "POST",
    headers: isFormData ? undefined : { "Content-Type": "application/json" },
    body: isFormData ? payload : JSON.stringify(payload),
  });
  if (!res.ok) {
    const errorBody = await res.text();
    throw new Error(`Turn submission failed (${res.status}): ${errorBody}`);
  }
  return res.json();
}

export async function submitTurnVoice(
  sessionId: string,
  audioBlob: Blob,
  options?: {
    textInput?: string;
    stepAnswers?: Record<string, string>;
    responseLatencySec?: number;
  }
): Promise<SubmitTurnResponse> {
  const fd = new FormData();
  fd.append("audio_file", audioBlob, "response.webm");
  if (options?.textInput) {
    fd.append("text_input", options.textInput);
  }
  if (options?.stepAnswers) {
    fd.append("step_answers", JSON.stringify(options.stepAnswers));
  }
  if (options?.responseLatencySec !== undefined) {
    fd.append("response_latency_sec", String(options.responseLatencySec));
  }
  return submitTurn(sessionId, fd);
}

export async function getSessionChunks(sessionId: string): Promise<ResourceChunk[]> {
  const res = await fetch(`${API_BASE}/api/v1/sessions/${encodeURIComponent(sessionId)}/chunks`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch document chunks (${res.status})`);
  }
  return res.json();
}

export async function injectSelfGuidedSnippet(
  sessionId: string,
  payload: SelfGuidedInjectRequest
): Promise<SelfGuidedInjectResponse> {
  const res = await fetch(
    `${API_BASE}/api/v1/sessions/${encodeURIComponent(sessionId)}/self-guided/inject`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    }
  );
  if (!res.ok) {
    const errorBody = await res.text();
    throw new Error(`Self-guided injection failed (${res.status}): ${errorBody}`);
  }
  return res.json();
}

export interface SelectConceptResponse {
  session: SessionState;
  action?: AgentActionPayload | null;
  exam?: MiniExamPayload | null;
}

export async function updateSessionMode(
  sessionId: string,
  mode: "AI_GUIDED" | "SELF_GUIDED"
): Promise<SessionState> {
  const res = await fetch(`${API_BASE}/api/v1/sessions/${encodeURIComponent(sessionId)}/mode`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ mode }),
  });
  if (!res.ok) {
    const errorBody = await res.text();
    throw new Error(`Failed to update session mode (${res.status}): ${errorBody}`);
  }
  return res.json();
}

export async function selectSessionConcept(
  sessionId: string,
  conceptId: string,
  targetStage: "FOUNDATION" | "PRACTICE" | "CHALLENGE" | "PROTEGE" | "EXAM" = "FOUNDATION"
): Promise<SelectConceptResponse> {
  const res = await fetch(
    `${API_BASE}/api/v1/sessions/${encodeURIComponent(sessionId)}/select-concept`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        concept_id: conceptId,
        target_stage: targetStage,
      }),
    }
  );
  if (!res.ok) {
    const errorBody = await res.text();
    throw new Error(`Failed to select concept (${res.status}): ${errorBody}`);
  }
  return res.json();
}

export async function startMiniExam(sessionId: string): Promise<MiniExamPayload> {
  const res = await fetch(`${API_BASE}/api/v1/sessions/${encodeURIComponent(sessionId)}/mini-exam/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const errorBody = await res.text();
    throw new Error(`Failed to start mini-exam (${res.status}): ${errorBody}`);
  }
  return res.json();
}

export async function submitMiniExam(
  sessionId: string,
  payload: ExamSubmitRequest
): Promise<ExamResult> {
  const res = await fetch(`${API_BASE}/api/v1/sessions/${encodeURIComponent(sessionId)}/mini-exam/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errorBody = await res.text();
    throw new Error(`Failed to submit mini-exam (${res.status}): ${errorBody}`);
  }
  return res.json();
}

export async function getStudentAnalytics(studentId: string): Promise<StudentAnalyticsDashboard> {
  const res = await fetch(`${API_BASE}/api/v1/students/${encodeURIComponent(studentId)}/analytics`, {
    cache: "no-store",
  });
  if (!res.ok) {
    const errorBody = await res.text();
    throw new Error(`Failed to fetch student analytics (${res.status}): ${errorBody}`);
  }
  return res.json();
}

