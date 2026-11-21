import { components, operations } from "@/types/api";

export type SessionState = components["schemas"]["SessionState"];
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
