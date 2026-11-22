"use client";

import React, { useEffect, useState, useTransition } from "react";
import {
  AgentActionPayload,
  FoundationBoardPayload,
  FadedWorkspacePayload,
  MisconceptionTrapPayload,
  ProtegeStagePayload,
  HealthCheckResponse,
  SessionState,
  DiagnosticQuestion,
  DiagnosticEvaluationResponse,
  SessionInitResponse,
  createMockSession,
  getHealthStatus,
  getSessionState,
  getSessionSlice,
} from "@/lib/api";
import { SessionOnboardingModal } from "@/components/SessionOnboardingModal";
import { BaselineDiagnosticCard } from "@/components/BaselineDiagnosticCard";
import { ConceptProgressStrip } from "@/components/ConceptProgressStrip";
import { FoundationBoard } from "@/components/FoundationBoard";
import { FadedWorkspace } from "@/components/FadedWorkspace";
import { ChallengeStage } from "@/components/ChallengeStage";
import { SelfGuidedReader } from "@/components/SelfGuidedReader";

export default function AdaptiveLearningPlatformPage() {
  // System Health State
  const [health, setHealth] = useState<HealthCheckResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState<boolean>(true);

  // Session & Action State
  const [session, setSession] = useState<SessionState | null>(null);
  const [action, setAction] = useState<AgentActionPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  // Slice 2 States
  const [isOnboardingOpen, setIsOnboardingOpen] = useState<boolean>(false);
  const [diagnosticQuestions, setDiagnosticQuestions] = useState<DiagnosticQuestion[]>([]);
  const [lastEvaluation, setLastEvaluation] = useState<DiagnosticEvaluationResponse | null>(null);
  const [contextSlice, setContextSlice] = useState<Record<string, unknown> | null>(null);
  const [isSliceDrawerOpen, setIsSliceDrawerOpen] = useState<boolean>(false);
  const [sliceLoading, setSliceLoading] = useState<boolean>(false);
  const [showReader, setShowReader] = useState<boolean>(false);

  // Quick Mock Controls
  const [studentId, setStudentId] = useState<string>("student_dev_01");
  const [domain, setDomain] = useState<string>("computer_science");
  const [topicTitle, setTopicTitle] = useState<string>("Recursion & Call Stacks");
  const [initialRating, setInitialRating] = useState<number>(0.25);

  // Redis Drawer
  const [isDrawerOpen, setIsDrawerOpen] = useState<boolean>(false);
  const [redisReloading, setRedisReloading] = useState<boolean>(false);
  const [redisMessage, setRedisMessage] = useState<string | null>(null);

  // Interactive Faded Step State

  const [showFlawAnswer, setShowFlawAnswer] = useState<boolean>(false);
  const [isRecording, setIsRecording] = useState<boolean>(false);

  // 1. Initial Health Probe
  const refreshHealth = async () => {
    setHealthLoading(true);
    try {
      const data = await getHealthStatus();
      setHealth(data);
    } catch (err: unknown) {
      console.error("Health check error:", err);
      setHealth(null);
    } finally {
      setHealthLoading(false);
    }
  };

  useEffect(() => {
    let isSubscribed = true;
    getHealthStatus()
      .then((data) => {
        if (isSubscribed) {
          setHealth(data);
          setHealthLoading(false);
        }
      })
      .catch((err) => {
        if (isSubscribed) {
          console.error("Health check error:", err);
          setHealth(null);
          setHealthLoading(false);
        }
      });
    return () => {
      isSubscribed = false;
    };
  }, []);

  // 2. Launch Mock Session via LangGraph (Slice 1 Fallback/Test)
  const handleLaunchMockSession = (rating: number) => {
    setInitialRating(rating);
    setError(null);
    setShowFlawAnswer(false);
    setDiagnosticQuestions([]);
    setLastEvaluation(null);

    startTransition(async () => {
      try {
        const response = await createMockSession({
          student_id: studentId,
          domain,
          topic_title: topicTitle,
          initial_rating: rating,
        });
        setSession(response.session);
        setAction(response.action);
        setRedisMessage(null);
      } catch (err: unknown) {
        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError("Failed to spawn mock session.");
        }
      }
    });
  };

  // 3. Slice 2: Session Initialized from Modal
  const handleSessionInitialized = (initData: SessionInitResponse) => {
    setSession(initData.session);
    setDiagnosticQuestions(initData.diagnostic_questions);
    setAction(null);
    setLastEvaluation(null);
    setError(null);
  };

  // 4. Slice 2: Diagnostic Submitted
  const handleDiagnosticCompleted = (evalResult: DiagnosticEvaluationResponse) => {
    setSession(evalResult.session);
    setAction(evalResult.action);
    setLastEvaluation(evalResult);
    setDiagnosticQuestions([]);
  };

  // 5. Slice 2: Fetch 1-Hop Slicer Context
  const handleFetchContextSlice = async () => {
    if (!session?.session_id) return;
    setSliceLoading(true);
    try {
      const sliceData = await getSessionSlice(session.session_id);
      setContextSlice(sliceData);
      setIsSliceDrawerOpen(true);
    } catch (err: unknown) {
      console.error("Error fetching slice:", err);
    } finally {
      setSliceLoading(false);
    }
  };

  // 6. Reload Session from Redis
  const handleReloadFromRedis = async () => {
    if (!session?.session_id) return;
    setRedisReloading(true);
    setRedisMessage(null);
    try {
      const freshSession = await getSessionState(session.session_id);
      setSession(freshSession);
      setRedisMessage(`Successfully reloaded session at ${new Date().toLocaleTimeString()}`);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setRedisMessage(`Redis read error: ${err.message}`);
      }
    } finally {
      setRedisReloading(false);
    }
  };

  // Render Action Payload Component
  const renderActionComponent = (act: AgentActionPayload) => {
    switch (act.ui_component) {
      case "FOUNDATION_BOARD":
        return renderFoundationBoard(act);
      case "FADED_EXAMPLE_WORKSPACE":
        return renderFadedWorkspace(act);
      case "MISCONCEPTION_TRAP":
        return renderMisconceptionTrap(act);
      case "PROTEGE_VOICE_STAGE":
        return renderProtegeStage(act);
      default: {
        const _exhaustiveCheck: never = act;
        return (
          <div className="p-4 bg-red-100 text-red-700 rounded-lg">
            Unknown UI Component: {JSON.stringify(_exhaustiveCheck)}
          </div>
        );
      }
    }
  };

  const renderFoundationBoard = (data: FoundationBoardPayload) => {
    if (!session) return null;
    return (
      <FoundationBoard
        payload={data}
        session={session}
        onUnderstandingChecked={(resp) => {
          setSession(resp.session);
          setAction(resp.action);
        }}
      />
    );
  };

  const renderFadedWorkspace = (data: FadedWorkspacePayload) => {
    if (!session) return null;
    return (
      <FadedWorkspace
        payload={data}
        session={session}
        onTurnSubmitted={(resp) => {
          setSession(resp.session);
          setAction(resp.action);
        }}
      />
    );
  };

  const renderMisconceptionTrap = (data: MisconceptionTrapPayload) => {
    if (!session) return null;
    return (
      <ChallengeStage
        payload={data}
        session={session}
        onTurnSubmitted={(resp) => {
          setSession(resp.session);
          setAction(resp.action);
        }}
      />
    );
  };

  const renderProtegeStage = (data: ProtegeStagePayload) => {
    if (!session) return null;
    return (
      <ChallengeStage
        payload={data}
        session={session}
        onTurnSubmitted={(resp) => {
          setSession(resp.session);
          setAction(resp.action);
        }}
      />
    );
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100">
      {/* Top Navigation & System Health Bar */}
      <header className="border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 px-6 py-4 shadow-sm sticky top-0 z-20">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-lg font-bold tracking-tight text-gray-900 dark:text-white">
                Adaptive AI Learning Platform
              </h1>
              <span className="px-2 py-0.5 text-xs font-mono font-semibold bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200 rounded">
                Slice 2: Multimodal Ingestion &amp; DAG
              </span>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              NetworkX DAG • Deterministic 1-Hop Slicer • Baseline Diagnostic • Gemini 3.8 Evaluator
            </p>
          </div>

          {/* Health Indicators & Onboarding Trigger */}
          <div className="flex items-center gap-3 flex-wrap">
            <button
              onClick={() => setIsOnboardingOpen(true)}
              className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold shadow-sm transition flex items-center gap-1.5"
            >
              <span>✨</span>
              <span>New Ingestion Session (Slice 2)</span>
            </button>

            <div className="flex items-center gap-2 text-xs flex-wrap">
              <button
                onClick={refreshHealth}
                disabled={healthLoading}
                className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded text-gray-500"
                title="Refresh Health"
              >
                🔄
              </button>
              <span
                className={`px-2 py-1 rounded-md font-mono flex items-center gap-1.5 border ${
                  health?.components?.postgres === "connected"
                    ? "bg-emerald-50 text-emerald-800 border-emerald-300 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800"
                    : "bg-rose-50 text-rose-800 border-rose-300 dark:bg-rose-950/40 dark:text-rose-300"
                }`}
              >
                <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                Postgres: {health?.components?.postgres || "connecting..."}
              </span>

              <span
                className={`px-2 py-1 rounded-md font-mono flex items-center gap-1.5 border ${
                  health?.components?.redis === "connected"
                    ? "bg-emerald-50 text-emerald-800 border-emerald-300 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800"
                    : "bg-rose-50 text-rose-800 border-rose-300 dark:bg-rose-950/40 dark:text-rose-300"
                }`}
              >
                <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                Redis: {health?.components?.redis || "connecting..."}
              </span>

              <span
                className={`px-2 py-1 rounded-md font-mono flex items-center gap-1.5 border ${
                  health?.components?.embeddings === "ready"
                    ? "bg-emerald-50 text-emerald-800 border-emerald-300 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800"
                    : "bg-rose-50 text-rose-800 border-rose-300 dark:bg-rose-950/40 dark:text-rose-300"
                }`}
              >
                <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                BGE-Embed: {health?.components?.embeddings || "loading..."}
              </span>

              <span
                className={`px-2 py-1 rounded-md font-mono flex items-center gap-1.5 border ${
                  health?.components?.whisper === "ready"
                    ? "bg-emerald-50 text-emerald-800 border-emerald-300 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800"
                    : "bg-rose-50 text-rose-800 border-rose-300 dark:bg-rose-950/40 dark:text-rose-300"
                }`}
              >
                <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                Whisper: {health?.components?.whisper || "loading..."}
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto px-6 py-8 grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Control Panel */}
        <div className="lg:col-span-4 space-y-6">
          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl p-5 shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                <span>🎛️</span>
                <span>Session Controls</span>
              </h2>
              <button
                type="button"
                onClick={() => setIsOnboardingOpen(true)}
                className="text-xs text-blue-600 dark:text-blue-400 font-semibold hover:underline"
              >
                + New Ingestion
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="font-semibold text-gray-700 dark:text-gray-300">
                  Student ID:
                </label>
                <input
                  type="text"
                  value={studentId}
                  onChange={(e) => setStudentId(e.target.value)}
                  className="mt-1 w-full px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 font-mono"
                />
              </div>

              <div>
                <label className="font-semibold text-gray-700 dark:text-gray-300">
                  Academic Domain:
                </label>
                <select
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                  className="mt-1 w-full px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 font-medium"
                >
                  <option value="computer_science">Computer Science</option>
                  <option value="biology">Cellular &amp; Molecular Biology</option>
                  <option value="mathematics">Discrete Mathematics</option>
                  <option value="physics">Classical &amp; Quantum Physics</option>
                </select>
              </div>

              <div>
                <label className="font-semibold text-gray-700 dark:text-gray-300">
                  Topic Title:
                </label>
                <input
                  type="text"
                  value={topicTitle}
                  onChange={(e) => setTopicTitle(e.target.value)}
                  className="mt-1 w-full px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 font-medium"
                />
              </div>
            </div>

            {/* Quick Trigger Tier Buttons */}
            <div className="pt-2 border-t border-gray-200 dark:border-gray-800 space-y-2">
              <label className="text-xs font-semibold text-gray-700 dark:text-gray-300">
                Trigger LangGraph Starter Skeleton:
              </label>
              <div className="grid grid-cols-1 gap-2">
                <button
                  type="button"
                  disabled={isPending}
                  onClick={() => handleLaunchMockSession(0.25)}
                  className={`px-3 py-2 rounded-xl text-xs font-semibold text-left transition flex items-center justify-between ${
                    initialRating === 0.25 && session && !diagnosticQuestions.length
                      ? "bg-sky-600 text-white"
                      : "bg-sky-50 dark:bg-sky-950/40 text-sky-800 dark:text-sky-200 border border-sky-300 dark:border-sky-800 hover:bg-sky-100"
                  }`}
                >
                  <span>1. Foundation Tier (Rating 0.25)</span>
                  <span className="font-mono text-[10px]">&lt; 40%</span>
                </button>

                <button
                  type="button"
                  disabled={isPending}
                  onClick={() => handleLaunchMockSession(0.55)}
                  className={`px-3 py-2 rounded-xl text-xs font-semibold text-left transition flex items-center justify-between ${
                    initialRating === 0.55 && session && !diagnosticQuestions.length
                      ? "bg-amber-600 text-white"
                      : "bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-200 border border-amber-300 dark:border-amber-800 hover:bg-amber-100"
                  }`}
                >
                  <span>2. Practice Tier (Rating 0.55)</span>
                  <span className="font-mono text-[10px]">40% – 75%</span>
                </button>

                <button
                  type="button"
                  disabled={isPending}
                  onClick={() => handleLaunchMockSession(0.85)}
                  className={`px-3 py-2 rounded-xl text-xs font-semibold text-left transition flex items-center justify-between ${
                    initialRating === 0.85 && session && !diagnosticQuestions.length
                      ? "bg-rose-600 text-white"
                      : "bg-rose-50 dark:bg-rose-950/40 text-rose-800 dark:text-rose-200 border border-rose-300 dark:border-rose-800 hover:bg-rose-100"
                  }`}
                >
                  <span>3. Deep Mastery Tier (Rating 0.85)</span>
                  <span className="font-mono text-[10px]">&gt; 75%</span>
                </button>
              </div>
            </div>

            {error && (
              <div className="p-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 rounded-lg text-xs text-red-700 dark:text-red-300">
                {error}
              </div>
            )}
          </div>

          {/* Redis Drawer & 1-Hop Slicer Trigger */}
          {session && (
            <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl p-4 shadow-sm space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-gray-700 dark:text-gray-300 flex items-center gap-1.5">
                  <span>💾</span>
                  <span>Redis &amp; Context Inspector</span>
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400">
                  TTL 24h
                </span>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 font-mono truncate">
                Key: session:{session.session_id}
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setIsDrawerOpen(!isDrawerOpen)}
                  className="px-3 py-1.5 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg text-xs font-medium"
                >
                  {isDrawerOpen ? "Hide Redis JSON" : "Inspect Redis"}
                </button>

                <button
                  type="button"
                  disabled={sliceLoading}
                  onClick={handleFetchContextSlice}
                  className="px-3 py-1.5 bg-purple-50 dark:bg-purple-950 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800 hover:bg-purple-100 rounded-lg text-xs font-semibold"
                >
                  {sliceLoading ? "Loading Slice..." : "🔍 1-Hop Slice"}
                </button>
              </div>

              <div className="pt-1 flex flex-col gap-2">
                <button
                  type="button"
                  disabled={redisReloading}
                  onClick={handleReloadFromRedis}
                  className="w-full px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-medium disabled:opacity-50"
                >
                  {redisReloading ? "Reloading..." : "Reload from Redis Cache"}
                </button>

                <button
                  type="button"
                  onClick={() => setShowReader(!showReader)}
                  className="w-full px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 shadow-sm"
                >
                  <span>📖</span>
                  <span>{showReader ? "Hide Document Reader" : "Open Document Reader"}</span>
                </button>
              </div>

              {redisMessage && (
                <p className="text-[11px] text-emerald-600 dark:text-emerald-400">
                  {redisMessage}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Right Column: Dynamic Workspace */}
        <div className="lg:col-span-8 space-y-6">
          {session ? (
            <div className="space-y-6">
              {/* Concept Progress Strip (Extracted DAG) */}
              <ConceptProgressStrip
                conceptGraph={session.concept_graph || []}
                activeConceptId={session.active_concept_id}
              />

              {/* Baseline Diagnostic Form (if questions pending) */}
              {diagnosticQuestions.length > 0 && (
                <BaselineDiagnosticCard
                  sessionId={session.session_id}
                  topicTitle={session.topic_title}
                  questions={diagnosticQuestions}
                  onDiagnosticCompleted={handleDiagnosticCompleted}
                />
              )}

              {/* Evaluation Feedback Banner (if diagnostic just completed) */}
              {lastEvaluation && (
                <div className="p-4 rounded-2xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold uppercase text-emerald-800 dark:text-emerald-300 flex items-center gap-1.5">
                      <span>🎯</span>
                      <span>Baseline Evaluation Completed</span>
                    </span>
                    <span className="font-mono text-xs font-bold px-2.5 py-0.5 rounded-full bg-emerald-200 dark:bg-emerald-800 text-emerald-900 dark:text-emerald-100">
                      Overall Rating: {(lastEvaluation.overall_initial_rating * 100).toFixed(0)}%
                    </span>
                  </div>
                  <p className="text-xs text-emerald-900 dark:text-emerald-200">
                    {lastEvaluation.summary}
                  </p>
                </div>
              )}

              {/* Active Pedagogical Component */}
              {action && renderActionComponent(action)}

              {/* Self-Guided Document Reader */}
              {showReader && session && (
                <SelfGuidedReader
                  session={session}
                  onSnippetInjected={(resp) => {
                    setSession(resp.session);
                    setAction(resp.action);
                    setShowReader(false);
                  }}
                  onClose={() => setShowReader(false)}
                />
              )}

              {/* 1-Hop Slicer Context Drawer */}
              {isSliceDrawerOpen && contextSlice && (
                <div className="bg-gray-900 border border-purple-500/50 rounded-2xl p-4 shadow-xl text-gray-100 space-y-2">
                  <div className="flex justify-between items-center border-b border-gray-800 pb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-purple-400 text-sm">🔍</span>
                      <span className="text-xs font-mono font-bold text-purple-300">
                        Deterministic 1-Hop Context Slice (Downstream Agent Context)
                      </span>
                    </div>
                    <button
                      onClick={() => setIsSliceDrawerOpen(false)}
                      className="text-xs text-gray-400 hover:text-white"
                    >
                      ✕ Close
                    </button>
                  </div>
                  <p className="text-[11px] text-gray-400">
                    Downstream LLMs only ever see this slice (active concept + top 2 resource chunks, immediate prerequisites, and next unlocked child):
                  </p>
                  <pre className="p-3 bg-gray-950 rounded-xl text-purple-300 font-mono text-xs overflow-x-auto max-h-96">
                    {JSON.stringify(contextSlice, null, 2)}
                  </pre>
                </div>
              )}

              {/* Live Redis Session JSON Inspector Drawer */}
              {isDrawerOpen && (
                <div className="bg-gray-900 border border-gray-800 rounded-2xl p-4 shadow-lg text-gray-100 space-y-2">
                  <div className="flex justify-between items-center border-b border-gray-800 pb-2">
                    <span className="text-xs font-mono font-bold text-gray-300">
                      Redis Snapshot: session:{session.session_id}
                    </span>
                    <button
                      onClick={() => setIsDrawerOpen(false)}
                      className="text-xs text-gray-400 hover:text-white"
                    >
                      ✕ Close
                    </button>
                  </div>
                  <pre className="p-3 bg-gray-950 rounded-xl text-emerald-400 font-mono text-xs overflow-x-auto max-h-96">
                    {JSON.stringify(session, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-white dark:bg-gray-900 border border-dashed border-gray-300 dark:border-gray-800 rounded-2xl p-12 text-center space-y-4">
              <span className="text-5xl">🚀</span>
              <h3 className="text-base font-bold text-gray-800 dark:text-gray-200">
                Adaptive AI Workspace Ready
              </h3>
              <p className="text-xs text-gray-500 dark:text-gray-400 max-w-md mx-auto">
                Start a full Multimodal Ingestion session with PDFs or YouTube/Web URLs, or trigger a quick mock session from the left control panel.
              </p>
              <button
                type="button"
                onClick={() => setIsOnboardingOpen(true)}
                className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold shadow-md transition inline-flex items-center gap-2"
              >
                <span>✨</span>
                <span>Open Session Onboarding Modal (Slice 2)</span>
              </button>
            </div>
          )}
        </div>
      </main>

      {/* Onboarding Modal */}
      <SessionOnboardingModal
        isOpen={isOnboardingOpen}
        onClose={() => setIsOnboardingOpen(false)}
        onSessionInitialized={handleSessionInitialized}
      />
    </div>
  );
}
