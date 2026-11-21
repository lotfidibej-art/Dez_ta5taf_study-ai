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
  createMockSession,
  getHealthStatus,
  getSessionState,
} from "@/lib/api";

export default function WalkingSkeletonPage() {
  // System Health State
  const [health, setHealth] = useState<HealthCheckResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState<boolean>(true);

  // Session & Action State
  const [session, setSession] = useState<SessionState | null>(null);
  const [action, setAction] = useState<AgentActionPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  // Form Controls
  const [studentId, setStudentId] = useState<string>("student_dev_01");
  const [domain, setDomain] = useState<string>("computer_science");
  const [topicTitle, setTopicTitle] = useState<string>("Recursion & Call Stacks");
  const [initialRating, setInitialRating] = useState<number>(0.25);

  // Redis Drawer
  const [isDrawerOpen, setIsDrawerOpen] = useState<boolean>(false);
  const [redisReloading, setRedisReloading] = useState<boolean>(false);
  const [redisMessage, setRedisMessage] = useState<string | null>(null);

  // Interactive Faded Step State
  const [userFadedInput, setUserFadedInput] = useState<string>("");
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

  // 2. Launch Mock Session via LangGraph
  const handleLaunchSession = (rating: number) => {
    setInitialRating(rating);
    setError(null);
    setShowFlawAnswer(false);
    setUserFadedInput("");

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

  // 3. Reload Session directly from Redis Cache
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

  // 4. Exhaustive Discriminator Switch Renderer
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

  const renderFoundationBoard = (data: FoundationBoardPayload) => (
    <div className="border border-sky-200 bg-sky-50/50 dark:bg-sky-950/20 dark:border-sky-800 rounded-xl p-6 shadow-sm space-y-6">
      <div className="flex items-center justify-between border-b border-sky-200 dark:border-sky-800 pb-3">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-sky-600 dark:text-sky-400">
            Mastery &lt; 0.40 • Foundation Board
          </span>
          <h3 className="text-xl font-bold text-gray-900 dark:text-gray-100">
            Core Mental Model Breakdown
          </h3>
        </div>
        <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-sky-100 text-sky-800 dark:bg-sky-900 dark:text-sky-200">
          Agent 4 &amp; 5: Explainer &amp; Labs
        </span>
      </div>

      {/* Bullet Breakdown */}
      <div className="space-y-2">
        <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
          Essential Concepts:
        </h4>
        <ul className="space-y-2">
          {data.bullet_breakdown.map((bullet, idx) => (
            <li key={idx} className="flex items-start gap-2 text-sm text-gray-800 dark:text-gray-200">
              <span className="text-sky-500 font-bold mt-0.5">•</span>
              <span>{bullet}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Mermaid Diagram Box */}
      {data.mermaid_diagram && (
        <div className="space-y-2">
          <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
            Structural Execution Flow (Mermaid Diagram):
          </h4>
          <pre className="p-4 rounded-lg bg-gray-900 text-sky-300 font-mono text-xs overflow-x-auto border border-gray-800">
            {data.mermaid_diagram}
          </pre>
        </div>
      )}

      {/* Bridge Analogy */}
      {data.bridge_analogy && (
        <div className="p-4 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-lg space-y-2">
          <div className="flex items-center gap-2 text-amber-800 dark:text-amber-300 font-semibold text-sm">
            <span>🌉</span>
            <span>Cross-Domain Bridge Analogy</span>
          </div>
          <div className="text-xs space-y-1 text-gray-700 dark:text-gray-300">
            <p>
              <strong className="text-amber-900 dark:text-amber-200">Source:</strong>{" "}
              {data.bridge_analogy.source_concept || JSON.stringify(data.bridge_analogy)}
            </p>
            {data.bridge_analogy.target_concept && (
              <p>
                <strong className="text-amber-900 dark:text-amber-200">Target:</strong>{" "}
                {data.bridge_analogy.target_concept}
              </p>
            )}
            {data.bridge_analogy.mapping && (
              <p className="italic text-gray-600 dark:text-gray-400 mt-1">
                &ldquo;{data.bridge_analogy.mapping}&rdquo;
              </p>
            )}
          </div>
        </div>
      )}

      {/* Interactive Lab Link & Study Nudge */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
        {data.interactive_lab && (
          <div className="p-3 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-gray-900 dark:text-gray-100">
                {data.interactive_lab.platform || "Interactive Sandbox"}
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {data.interactive_lab.instruction}
              </p>
            </div>
            {data.interactive_lab.lab_url && (
              <a
                href={data.interactive_lab.lab_url}
                target="_blank"
                rel="noreferrer"
                className="ml-3 px-3 py-1.5 bg-sky-600 text-white rounded text-xs font-medium hover:bg-sky-700 transition"
              >
                Launch Lab ↗
              </a>
            )}
          </div>
        )}

        {data.study_habit_nudge && (
          <div className="p-3 bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 rounded-lg">
            <p className="text-xs font-semibold text-emerald-800 dark:text-emerald-300">
              💡 Study Habit Nudge
            </p>
            <p className="text-xs text-emerald-700 dark:text-emerald-400 mt-0.5">
              {data.study_habit_nudge}
            </p>
          </div>
        )}
      </div>
    </div>
  );

  const renderFadedWorkspace = (data: FadedWorkspacePayload) => (
    <div className="border border-amber-200 bg-amber-50/40 dark:bg-amber-950/20 dark:border-amber-800 rounded-xl p-6 shadow-sm space-y-6">
      <div className="flex items-center justify-between border-b border-amber-200 dark:border-amber-800 pb-3">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-amber-600 dark:text-amber-400">
            Mastery 0.40 – 0.75 • Guided Practice
          </span>
          <h3 className="text-xl font-bold text-gray-900 dark:text-gray-100">
            Faded Worked Example Workspace
          </h3>
        </div>
        <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200">
          Agent 6: Scaffolding
        </span>
      </div>

      <div className="p-3 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg">
        <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">
          Problem Objective:
        </span>
        <p className="text-sm font-medium text-gray-900 dark:text-gray-100 mt-1">
          {data.problem_statement}
        </p>
      </div>

      {/* Step Sequence */}
      <div className="space-y-4">
        <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
          Guided Steps:
        </h4>
        {data.steps.map((step, idx) => {
          const isWorked = step.step_type === "WORKED";
          return (
            <div
              key={idx}
              className={`p-4 rounded-lg border transition ${
                isWorked
                  ? "bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800"
                  : "bg-amber-100/60 dark:bg-amber-900/40 border-amber-400 dark:border-amber-600 shadow-sm"
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span
                    className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                      isWorked
                        ? "bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-200"
                        : "bg-amber-500 text-white"
                    }`}
                  >
                    {idx + 1}
                  </span>
                  <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                    {String(step.label || `Step ${idx + 1}`)}
                  </span>
                </div>
                <span
                  className={`text-xs px-2 py-0.5 rounded font-mono ${
                    isWorked
                      ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200"
                      : "bg-amber-200 text-amber-900 dark:bg-amber-800 dark:text-amber-100 font-bold"
                  }`}
                >
                  {isWorked ? "WORKED" : "FADED • COMPLETE THIS"}
                </span>
              </div>

              {/* Code representation */}
              {isWorked ? (
                <pre className="p-3 rounded bg-gray-950 text-emerald-400 font-mono text-xs overflow-x-auto">
                  {String(step.code || "")}
                </pre>
              ) : (
                <div className="space-y-2 mt-2">
                  <pre className="p-3 rounded bg-gray-950 text-amber-300 font-mono text-xs overflow-x-auto">
                    {String(step.code || "return n + _______")}
                  </pre>
                  <div className="flex gap-2 items-center">
                    <input
                      type="text"
                      placeholder="Type the missing recursive call..."
                      value={userFadedInput}
                      onChange={(e) => setUserFadedInput(e.target.value)}
                      className="flex-1 px-3 py-1.5 text-xs rounded border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 font-mono"
                    />
                    <button
                      type="button"
                      onClick={() => alert(`Submitted response: ${userFadedInput}`)}
                      className="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded text-xs font-semibold"
                    >
                      Check Answer
                    </button>
                  </div>
                </div>
              )}

              {step.annotation ? (
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-2 italic">
                  Note: {String(step.annotation)}
                </p>
              ) : null}
            </div>
          );
        })}
      </div>

      {/* Active Hint Ladder */}
      {data.active_hint && (
        <div className="p-3 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg text-xs space-y-1">
          <span className="font-semibold text-blue-800 dark:text-blue-300">
            🔍 Level {String(data.active_hint.level || 1)} Contingent Hint:
          </span>
          <p className="text-blue-700 dark:text-blue-200">
            {String(data.active_hint.hint_text || JSON.stringify(data.active_hint))}
          </p>
        </div>
      )}
    </div>
  );

  const renderMisconceptionTrap = (data: MisconceptionTrapPayload) => (
    <div className="border border-rose-200 bg-rose-50/50 dark:bg-rose-950/20 dark:border-rose-800 rounded-xl p-6 shadow-sm space-y-6">
      <div className="flex items-center justify-between border-b border-rose-200 dark:border-rose-800 pb-3">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-rose-600 dark:text-rose-400">
            Mastery &gt; 0.75 • Deep Mastery Challenge
          </span>
          <h3 className="text-xl font-bold text-gray-900 dark:text-gray-100">
            Adversarial Misconception Trap
          </h3>
        </div>
        <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-rose-100 text-rose-800 dark:bg-rose-900 dark:text-rose-200">
          Agent 7: Adversarial
        </span>
      </div>

      <div className="p-3 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg">
        <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">
          Challenge Scenario:
        </span>
        <p className="text-sm font-medium text-gray-900 dark:text-gray-100 mt-1">
          {data.scenario_intro}
        </p>
      </div>

      <div className="space-y-2">
        <div className="flex justify-between items-center">
          <span className="text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase">
            Flawed Artifact ({data.artifact_language}):
          </span>
          <span className="text-xs text-rose-600 font-semibold">
            ⚠️ Contains 1 Subtle Conceptual Flaw
          </span>
        </div>
        <pre className="p-4 rounded-lg bg-gray-950 text-rose-300 font-mono text-xs overflow-x-auto border border-rose-900/50">
          {data.flawed_artifact}
        </pre>
      </div>

      <div className="pt-2 flex items-center justify-between">
        <button
          type="button"
          onClick={() => setShowFlawAnswer(!showFlawAnswer)}
          className="text-xs font-semibold text-rose-600 hover:text-rose-700 underline"
        >
          {showFlawAnswer ? "Hide Hidden Flaw Tag" : "Reveal Ground-Truth Flaw Tag"}
        </button>

        {showFlawAnswer && (
          <span className="px-3 py-1 bg-rose-200 dark:bg-rose-900 text-rose-900 dark:text-rose-100 rounded text-xs font-mono font-bold">
            {data.hidden_flaw_tag}
          </span>
        )}
      </div>
    </div>
  );

  const renderProtegeStage = (data: ProtegeStagePayload) => (
    <div className="border border-purple-200 bg-purple-50/50 dark:bg-purple-950/20 dark:border-purple-800 rounded-xl p-6 shadow-sm space-y-6">
      <div className="flex items-center justify-between border-b border-purple-200 dark:border-purple-800 pb-3">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-purple-600 dark:text-purple-400">
            Mastery &gt; 0.75 • Protégé Mode
          </span>
          <h3 className="text-xl font-bold text-gray-900 dark:text-gray-100">
            Teach the AI Student (Voice Analysis Enabled)
          </h3>
        </div>
        <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">
          Agent 7: Protégé Voice
        </span>
      </div>

      <div className="p-4 bg-white dark:bg-gray-900 border-l-4 border-purple-500 rounded-r-lg">
        <p className="text-xs font-bold text-purple-600 uppercase tracking-wider">
          AI Student Persona Asks:
        </p>
        <p className="text-base font-semibold text-gray-900 dark:text-gray-100 mt-1 italic">
          &ldquo;{data.ai_persona_question}&rdquo;
        </p>
      </div>

      <div className="space-y-2">
        <h4 className="text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase">
          Required Causal Explanation Points:
        </h4>
        <ul className="space-y-1.5">
          {data.target_explanation_points.map((pt, idx) => (
            <li key={idx} className="flex items-center gap-2 text-xs text-gray-700 dark:text-gray-300">
              <span className="text-purple-500 font-bold">✓</span>
              <span>{pt}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="pt-2 flex items-center gap-4">
        <button
          type="button"
          onClick={() => setIsRecording(!isRecording)}
          className={`px-4 py-2 rounded-lg text-xs font-bold flex items-center gap-2 transition ${
            isRecording
              ? "bg-red-600 text-white animate-pulse"
              : "bg-purple-600 hover:bg-purple-700 text-white"
          }`}
        >
          <span>🎙️</span>
          <span>{isRecording ? "Listening & Extracting Prosody..." : "Record Voice Answer"}</span>
        </button>
        {isRecording && (
          <span className="text-xs text-gray-500 animate-pulse">
            Analyzing speech rate, pauses, and hesitation metrics via faster-whisper...
          </span>
        )}
      </div>
    </div>
  );

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
              <span className="px-2 py-0.5 text-xs font-mono font-semibold bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 rounded">
                Slice 1: Walking Skeleton
              </span>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              LangGraph State Machine • Discriminated UI Routing • Redis Contract Cache
            </p>
          </div>

          {/* Health Indicators */}
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
      </header>

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto px-6 py-8 grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Control Panel */}
        <div className="lg:col-span-4 space-y-6">
          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-5 shadow-sm space-y-4">
            <h2 className="text-base font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
              <span>🎛️</span>
              <span>Session Starter Controls</span>
            </h2>

            <div className="space-y-3 text-xs">
              <div>
                <label className="font-semibold text-gray-700 dark:text-gray-300">
                  Student ID:
                </label>
                <input
                  type="text"
                  value={studentId}
                  onChange={(e) => setStudentId(e.target.value)}
                  className="mt-1 w-full px-3 py-1.5 rounded border border-gray-300 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 font-mono"
                />
              </div>

              <div>
                <label className="font-semibold text-gray-700 dark:text-gray-300">
                  Academic Domain:
                </label>
                <select
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                  className="mt-1 w-full px-3 py-1.5 rounded border border-gray-300 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 font-medium"
                >
                  <option value="computer_science">Computer Science</option>
                  <option value="biology">Cellular &amp; Molecular Biology</option>
                  <option value="mathematics">Discrete Mathematics</option>
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
                  className="mt-1 w-full px-3 py-1.5 rounded border border-gray-300 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 font-medium"
                />
              </div>
            </div>

            {/* Quick Trigger Tier Buttons */}
            <div className="pt-2 border-t border-gray-200 dark:border-gray-800 space-y-2">
              <label className="text-xs font-semibold text-gray-700 dark:text-gray-300">
                Trigger LangGraph State Machine:
              </label>
              <div className="grid grid-cols-1 gap-2">
                <button
                  type="button"
                  disabled={isPending}
                  onClick={() => handleLaunchSession(0.25)}
                  className={`px-3 py-2 rounded-lg text-xs font-semibold text-left transition flex items-center justify-between ${
                    initialRating === 0.25 && session
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
                  onClick={() => handleLaunchSession(0.55)}
                  className={`px-3 py-2 rounded-lg text-xs font-semibold text-left transition flex items-center justify-between ${
                    initialRating === 0.55 && session
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
                  onClick={() => handleLaunchSession(0.85)}
                  className={`px-3 py-2 rounded-lg text-xs font-semibold text-left transition flex items-center justify-between ${
                    initialRating === 0.85 && session
                      ? "bg-rose-600 text-white"
                      : "bg-rose-50 dark:bg-rose-950/40 text-rose-800 dark:text-rose-200 border border-rose-300 dark:border-rose-800 hover:bg-rose-100"
                  }`}
                >
                  <span>3. Deep Mastery Tier (Rating 0.85)</span>
                  <span className="font-mono text-[10px]">&gt; 75%</span>
                </button>
              </div>
            </div>

            {/* Error Message */}
            {error && (
              <div className="p-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 rounded-lg text-xs text-red-700 dark:text-red-300">
                {error}
              </div>
            )}
          </div>

          {/* Redis Drawer Trigger */}
          {session && (
            <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4 shadow-sm space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-gray-700 dark:text-gray-300 flex items-center gap-1.5">
                  <span>💾</span>
                  <span>Redis Session Cache</span>
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400">
                  TTL 24h
                </span>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 font-mono">
                Key: session:{session.session_id}
              </p>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setIsDrawerOpen(!isDrawerOpen)}
                  className="flex-1 px-3 py-1.5 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 rounded text-xs font-medium"
                >
                  {isDrawerOpen ? "Hide State JSON" : "Inspect State JSON"}
                </button>
                <button
                  type="button"
                  disabled={redisReloading}
                  onClick={handleReloadFromRedis}
                  className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded text-xs font-medium disabled:opacity-50"
                >
                  {redisReloading ? "..." : "Reload from Redis"}
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
              {/* Active Session Meta Card */}
              <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-5 shadow-sm space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <span className="text-xs font-mono text-gray-400">
                      ID: {session.session_id}
                    </span>
                    <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100">
                      {session.topic_title}
                    </h2>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono px-2 py-1 bg-gray-100 dark:bg-gray-800 rounded text-gray-700 dark:text-gray-300">
                      Mode: {session.mode}
                    </span>
                    <span className="text-xs font-mono px-2 py-1 bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-300 rounded border border-blue-200 dark:border-blue-800">
                      Last Tech: {session.last_technique_used}
                    </span>
                  </div>
                </div>

                {/* Concept Nodes Progress */}
                <div className="space-y-1.5 pt-2 border-t border-gray-100 dark:border-gray-800">
                  <div className="flex justify-between text-xs text-gray-500">
                    <span>Syllabus Concept Graph</span>
                    <span>Active: {session.active_concept_id}</span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                    {(session.concept_graph ?? []).map((node) => (
                      <div
                        key={node.concept_id}
                        className={`p-2.5 rounded-lg border text-xs ${
                          node.concept_id === session.active_concept_id
                            ? "border-blue-500 bg-blue-50/50 dark:bg-blue-950/40"
                            : "border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900"
                        }`}
                      >
                        <div className="font-semibold truncate text-gray-900 dark:text-gray-100">
                          {node.title}
                        </div>
                        <div className="flex justify-between items-center mt-1 text-[11px] text-gray-500">
                          <span>Rating: {(node.mastery_rating * 100).toFixed(0)}%</span>
                          <span
                            className={`px-1.5 py-0.2 rounded font-mono text-[10px] ${
                              node.status === "MASTERED"
                                ? "bg-emerald-100 text-emerald-800"
                                : node.status === "ACTIVE"
                                ? "bg-blue-100 text-blue-800"
                                : "bg-gray-200 text-gray-700"
                            }`}
                          >
                            {node.status}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Action Component Rendered via Discriminated Union */}
              {action && renderActionComponent(action)}

              {/* Live Redis Session JSON Inspector Drawer */}
              {isDrawerOpen && (
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 shadow-lg text-gray-100 space-y-2">
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
                  <pre className="p-3 bg-gray-950 rounded text-emerald-400 font-mono text-xs overflow-x-auto max-h-96">
                    {JSON.stringify(session, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-white dark:bg-gray-900 border border-dashed border-gray-300 dark:border-gray-800 rounded-xl p-12 text-center space-y-3">
              <span className="text-4xl">🚀</span>
              <h3 className="text-base font-bold text-gray-800 dark:text-gray-200">
                Walking Skeleton Console Ready
              </h3>
              <p className="text-xs text-gray-500 dark:text-gray-400 max-w-md mx-auto">
                Choose an initial mastery rating on the left control panel to trigger the LangGraph
                state machine and render the corresponding discriminated UI component.
              </p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
