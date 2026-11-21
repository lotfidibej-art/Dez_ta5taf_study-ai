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
  payload: UnderstandingCheckRequest
): Promise<UnderstandingCheckResponse> {
  const res = await fetch(
    `${API_BASE}/api/v1/sessions/${encodeURIComponent(sessionId)}/check-understanding`,
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
    throw new Error(`Understanding check failed (${res.status}): ${errorBody}`);
  }
  return res.json();
}
