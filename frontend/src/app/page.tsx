"use client";

import React, { useEffect, useState, useTransition } from "react";
import { motion, AnimatePresence } from "framer-motion";
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
  ResourceChunk,
  MiniExamPayload,
  ExamResult,
  createMockSession,
  getHealthStatus,
  getSessionState,
  getSessionSlice,
  getSessionChunks,
  startMiniExam,
  updateSessionMode,
  selectSessionConcept,
} from "@/lib/api";
import Navbar from "@/components/Navbar";
import ConceptSkillTree from "@/components/ConceptSkillTree";
import TelemetryDrawer from "@/components/TelemetryDrawer";
import MiniExamModal from "@/components/MiniExamModal";
import RemediationPanel from "@/components/RemediationPanel";
import { SessionOnboardingModal } from "@/components/SessionOnboardingModal";
import { BaselineDiagnosticCard } from "@/components/BaselineDiagnosticCard";
import { FoundationBoard } from "@/components/FoundationBoard";
import { FadedWorkspace } from "@/components/FadedWorkspace";
import { ChallengeStage } from "@/components/ChallengeStage";
import { SelfGuidedReader } from "@/components/SelfGuidedReader";
import {
  Sparkles,
  BookOpen,
  GraduationCap,
  LayoutGrid,
  Layers,
  ChevronLeft,
  ChevronRight,
  Activity,
  Award,
  RefreshCw,
  Plus,
  Compass,
  Zap,
} from "lucide-react";

export default function AdaptiveStudyStudioPage() {
  // System Health
  const [health, setHealth] = useState<HealthCheckResponse | null>(null);

  // Session & Action
  const [session, setSession] = useState<SessionState | null>(null);
  const [action, setAction] = useState<AgentActionPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  // Resource Chunks & Slices
  const [chunks, setChunks] = useState<ResourceChunk[]>([]);
  const [contextSlice, setContextSlice] = useState<Record<string, unknown> | null>(null);

  // Layout Drawers
  const [leftRailOpen, setLeftRailOpen] = useState(true);
  const [rightDrawerOpen, setRightDrawerOpen] = useState(true);

  // Modals & Panels
  const [isOnboardingOpen, setIsOnboardingOpen] = useState(false);
  const [diagnosticQuestions, setDiagnosticQuestions] = useState<DiagnosticQuestion[]>([]);
  const [showReader, setShowReader] = useState(false);
  const [miniExamPayload, setMiniExamPayload] = useState<MiniExamPayload | null>(null);
  const [isExamLoading, setIsExamLoading] = useState(false);

  // Prosody / Last feedback signals
  const [lastProsodySignals, setLastProsodySignals] = useState<any>(null);
  const [lastStudyHabitNudge, setLastStudyHabitNudge] = useState<string | null>(null);

  // 1. Initial Health Check
  useEffect(() => {
    getHealthStatus()
      .then((data) => setHealth(data))
      .catch((err) => console.error("Health probe error:", err));
  }, []);

  // 2. Fetch primary document chunks whenever session changes
  useEffect(() => {
    if (session?.session_id) {
      getSessionChunks(session.session_id)
        .then((data) => setChunks(data))
        .catch(() => setChunks([]));
    }
  }, [session?.session_id]);

  // 3. Launch Starter Session
  const handleLaunchStarterSession = (
    rating: number = 0.35,
    mode: "AI_GUIDED" | "SELF_GUIDED" = "AI_GUIDED"
  ) => {
    setError(null);
    setDiagnosticQuestions([]);
    setShowReader(mode === "SELF_GUIDED");

    startTransition(async () => {
      try {
        const response = await createMockSession({
          student_id: "student_dev_01",
          domain: "computer_science",
          topic_title: "Breadth-First Search & Graph Traversal",
          initial_rating: rating,
          mode,
        });
        setSession(response.session);
        setAction(response.action);
      } catch (err: any) {
        setError(err.message || "Failed to initialize studio session.");
      }
    });
  };

  // Toggle Mode (AI-Guided vs Self-Guided)
  const handleToggleMode = async (newMode: "AI_GUIDED" | "SELF_GUIDED") => {
    if (!session || session.mode === newMode) return;
    try {
      const updated = await updateSessionMode(session.session_id, newMode);
      setSession(updated);
      if (newMode === "SELF_GUIDED") {
        setShowReader(false);
      }
    } catch (err: unknown) {
      console.error("Failed to switch mode", err);
    }
  };

  // Self-Guided Target Stage Selection
  const handleSelectLessonStage = async (
    conceptId: string,
    stage: "FOUNDATION" | "PRACTICE" | "CHALLENGE" | "PROTEGE" | "EXAM"
  ) => {
    if (!session) return;
    startTransition(async () => {
      try {
        const resp = await selectSessionConcept(session.session_id, conceptId, stage);
        setSession(resp.session);
        if (resp.exam) {
          setMiniExamPayload(resp.exam);
        } else if (resp.action) {
          setAction(resp.action);
          setShowReader(false);
        }
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to load requested lesson stage");
      }
    });
  };

  // 4. Session Initialized from Onboarding Modal
  const handleSessionInitialized = (initData: SessionInitResponse) => {
    setSession(initData.session);
    setDiagnosticQuestions(initData.diagnostic_questions || []);
    setAction(null);
    setError(null);
    setShowReader(initData.session.mode === "SELF_GUIDED");
  };

  // 5. Diagnostic Evaluation Completed
  const handleDiagnosticCompleted = (evalResult: DiagnosticEvaluationResponse) => {
    setSession(evalResult.session);
    setAction(evalResult.action);
    setDiagnosticQuestions([]);
  };

  // 6. Trigger Adaptive Mini-Exam
  const handleStartMiniExam = async () => {
    if (!session?.session_id) return;
    setIsExamLoading(true);
    setError(null);
    try {
      const exam = await startMiniExam(session.session_id);
      setMiniExamPayload(exam);
    } catch (err: any) {
      setError(err.message || "Could not launch adaptive mini-exam.");
    } finally {
      setIsExamLoading(false);
    }
  };

  // Compute Active Concept & Overall Comprehension Rating
  const activeConcept = session?.concept_graph?.find(
    (c) => c.concept_id === session.active_concept_id
  );
  const activeRating = activeConcept ? activeConcept.mastery_rating : 0.0;
  const ratingPct = Math.round(activeRating * 100);

  // Semantic Tier Styling
  const getTierDetails = (rating: number) => {
    if (rating < 0.4) {
      return {
        name: "Foundation",
        textColor: "text-sky-600 dark:text-sky-400",
        bgColor: "bg-sky-500",
        badgeColor: "bg-sky-500/10 text-sky-700 dark:text-sky-300 border-sky-500/30",
      };
    }
    if (rating < 0.75) {
      return {
        name: "Guided Practice",
        textColor: "text-purple-600 dark:text-purple-400",
        bgColor: "bg-purple-500",
        badgeColor: "bg-purple-500/10 text-purple-700 dark:text-purple-300 border-purple-500/30",
      };
    }
    return {
      name: "Deep Mastery",
      textColor: "text-emerald-600 dark:text-emerald-400",
      bgColor: "bg-emerald-500",
      badgeColor: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30",
    };
  };

  const tier = getTierDetails(activeRating);

  return (
    <div className="min-h-screen flex flex-col bg-transparent text-slate-900 dark:text-zinc-100 transition-colors">
      <Navbar
        activeSessionTopic={session?.topic_title}
        comprehensionRating={activeRating}
      />

      {/* Top Session Control Strip */}
      {session && (
        <div className="border-b border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/90 px-4 sm:px-6 py-2.5 backdrop-blur-md">
          <div className="max-w-7xl mx-auto flex flex-col lg:flex-row lg:items-center justify-between gap-3">
            {/* Topic & Badges */}
            <div className="flex items-center gap-3 flex-wrap">
              <span className="font-bold text-sm tracking-tight text-slate-900 dark:text-zinc-100">
                {session.topic_title}
              </span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-slate-100 dark:bg-zinc-800 text-slate-700 dark:text-zinc-300 border border-slate-200 dark:border-zinc-700">
                {session.domain.toUpperCase().replace("_", " ")}
              </span>
              <div className="flex items-center gap-1 bg-slate-100 dark:bg-zinc-800/80 p-0.5 rounded-lg border border-slate-200 dark:border-zinc-700">
                <button
                  type="button"
                  onClick={() => handleToggleMode("AI_GUIDED")}
                  className={`px-2 py-0.5 rounded-md text-[10px] font-mono font-semibold transition-all ${
                    session.mode === "AI_GUIDED"
                      ? "bg-indigo-600 text-white shadow-2xs"
                      : "text-slate-600 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-zinc-200"
                  }`}
                  title="AI-Guided: System automatically manages prerequisite sequencing and mastery thresholds"
                >
                  AI-Guided
                </button>
                <button
                  type="button"
                  onClick={() => handleToggleMode("SELF_GUIDED")}
                  className={`px-2 py-0.5 rounded-md text-[10px] font-mono font-semibold transition-all ${
                    session.mode === "SELF_GUIDED"
                      ? "bg-amber-600 text-white shadow-2xs"
                      : "text-slate-600 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-zinc-200"
                  }`}
                  title="Self-Guided: Freely pick any concept, lesson format, or test without locked prerequisites"
                >
                  Self-Guided
                </button>
              </div>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-mono text-slate-500 dark:text-zinc-400 border border-slate-200 dark:border-zinc-800">
                {session.resource_scope.replace("_", " ")}
              </span>
            </div>

            {/* Comprehension Rating Meter & Actions */}
            <div className="flex items-center gap-4 flex-wrap">
              {/* Animated Meter */}
              <div className="flex items-center gap-2.5">
                <span className="text-xs font-semibold text-slate-500 dark:text-zinc-400">
                  Concept Mastery:
                </span>
                <div className="w-28 h-2 bg-slate-100 dark:bg-zinc-800 rounded-full overflow-hidden border border-slate-200 dark:border-zinc-700/60">
                  <div
                    className={`h-full ${tier.bgColor} transition-all duration-700 rounded-full`}
                    style={{ width: `${ratingPct}%` }}
                  />
                </div>
                <span className={`font-mono text-xs font-bold ${tier.textColor}`}>
                  {ratingPct}%
                </span>
                <span className={`text-[10px] px-2 py-0.5 rounded-full border font-semibold ${tier.badgeColor}`}>
                  {tier.name}
                </span>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowReader(!showReader)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all ${
                    showReader
                      ? "bg-indigo-600 text-white border-indigo-600 shadow-2xs"
                      : "bg-slate-50 dark:bg-zinc-800 border-slate-200 dark:border-zinc-700 text-slate-700 dark:text-zinc-300 hover:bg-slate-100"
                  }`}
                >
                  <BookOpen className="w-3.5 h-3.5" />
                  <span>{showReader ? "Studio Mode" : "Reader Mode"}</span>
                </button>

                <button
                  onClick={handleStartMiniExam}
                  disabled={isExamLoading}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50 transition-all shadow-xs"
                >
                  <Award className="w-3.5 h-3.5" />
                  <span>{isExamLoading ? "Generating..." : "Take Mini-Exam"}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main Studio Viewport (3-Zone Layout) */}
      <div className="flex-1 flex overflow-hidden">
        {/* Zone 1: Left Rail (Concept Skill Tree & Citations) */}
        {session && leftRailOpen && (
          <aside className="w-72 lg:w-80 flex-shrink-0 h-[calc(100vh-89px)] border-r border-slate-200 dark:border-zinc-800 animate-in slide-in-from-left duration-200">
              <ConceptSkillTree
                concepts={session.concept_graph || []}
                activeConceptId={session.active_concept_id}
                mode={session.mode}
                chunks={chunks}
                onSelectConcept={(id) => {
                  const node = (session.concept_graph || []).find((c) => c.concept_id === id);
                  if (node && (session.mode === "SELF_GUIDED" || node.status !== "LOCKED")) {
                    setSession({ ...session, active_concept_id: id });
                  }
                }}
                onSelectLessonStage={handleSelectLessonStage}
              />
          </aside>
        )}

        {/* Zone 2: Center Focus Stage (Pedagogical Canvas) */}
        <main className="flex-1 overflow-y-auto h-[calc(100vh-89px)] p-4 sm:p-6 flex flex-col space-y-4">
          {error && (
            <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-600 dark:text-rose-400 flex items-center justify-between">
              <span>{error}</span>
              <button onClick={() => setError(null)} className="text-xs font-bold underline">
                Dismiss
              </button>
            </div>
          )}

          {!session ? (
            /* Welcome / Starter Hero when no session is active */
            <div className="flex-1 flex items-center justify-center p-6">
              <div className="max-w-xl text-center space-y-6">
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 text-white mx-auto shadow-xl">
                  <Sparkles className="w-8 h-8" />
                </div>
                <div className="space-y-2">
                  <h2 className="text-2xl font-extrabold tracking-tight text-slate-900 dark:text-zinc-100">
                    Welcome to headRook
                  </h2>
                  <p className="text-xs sm:text-sm text-slate-600 dark:text-zinc-400 leading-relaxed max-w-md mx-auto">
                    Experience dynamic domain DAG sequencing, real-time Whisper prosody analysis, targeted counter-examples, and multi-armed bandit personalization.
                  </p>
                </div>

                <div className="flex flex-col sm:flex-row items-center justify-center gap-2.5 pt-2 flex-wrap">
                  <button
                    onClick={() => setIsOnboardingOpen(true)}
                    className="w-full sm:w-auto px-4 py-2.5 rounded-xl text-xs font-bold bg-indigo-600 text-white hover:bg-indigo-700 shadow-md transition-all flex items-center justify-center gap-1.5"
                  >
                    <Plus className="w-4 h-4" />
                    <span>Start Ingestion Session</span>
                  </button>

                  <button
                    onClick={() => handleLaunchStarterSession(0.35, "AI_GUIDED")}
                    className="w-full sm:w-auto px-4 py-2.5 rounded-xl text-xs font-semibold bg-slate-100 dark:bg-zinc-800 text-slate-800 dark:text-zinc-200 hover:bg-slate-200 dark:hover:bg-zinc-700 transition-all border border-slate-200 dark:border-zinc-700 flex items-center justify-center gap-1.5"
                  >
                    <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
                    <span>Launch AI-Guided Lab</span>
                  </button>

                  <button
                    onClick={() => handleLaunchStarterSession(0.35, "SELF_GUIDED")}
                    className="w-full sm:w-auto px-4 py-2.5 rounded-xl text-xs font-semibold bg-amber-500/10 text-amber-700 dark:text-amber-300 hover:bg-amber-500/20 transition-all border border-amber-500/30 flex items-center justify-center gap-1.5"
                  >
                    <Compass className="w-3.5 h-3.5 text-amber-500" />
                    <span>Launch Self-Guided Lab</span>
                  </button>
                </div>
              </div>
            </div>
          ) : (
            /* Active Learning Canvas */
            <div className="flex-1 flex flex-col space-y-4">
              {/* Rail Toggle Pill */}
              <div className="flex items-center justify-between text-xs text-slate-500 dark:text-zinc-400">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setLeftRailOpen(!leftRailOpen)}
                    className="flex items-center gap-1 px-2.5 py-1 rounded-lg border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors text-[11px]"
                  >
                    {leftRailOpen ? <ChevronLeft className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                    <span>{leftRailOpen ? "Hide Skill Tree" : "Show Skill Tree"}</span>
                  </button>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setRightDrawerOpen(!rightDrawerOpen)}
                    className="flex items-center gap-1 px-2.5 py-1 rounded-lg border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors text-[11px]"
                  >
                    <span>{rightDrawerOpen ? "Hide Telemetry" : "Show Telemetry"}</span>
                    {rightDrawerOpen ? <ChevronRight className="w-3.5 h-3.5" /> : <ChevronLeft className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>

              {/* Inline Remediation Callout if active */}
              {session.active_remediation && (
                <RemediationPanel
                  remediation={session.active_remediation}
                  onDismiss={() => {
                    setSession({ ...session, active_remediation: null });
                  }}
                />
              )}

              {/* Pedagogical Stage Morphing with AnimatePresence */}
              <AnimatePresence mode="wait">
                <motion.div
                  key={
                    showReader
                      ? "reader"
                      : diagnosticQuestions.length > 0
                      ? "diagnostic"
                      : action?.ui_component || "workspace"
                  }
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.2 }}
                  className="flex-1 flex flex-col"
                >
                  {/* Mode 1: Self-Guided Reader */}
                  {showReader ? (
                    <SelfGuidedReader
                      session={session}
                      onSnippetInjected={(resp) => {
                        setSession(resp.session);
                        setAction(resp.action);
                        setShowReader(false);
                      }}
                      onClose={() => setShowReader(false)}
                    />
                  ) : diagnosticQuestions.length > 0 ? (
                    /* Mode 2: Baseline Diagnostic Questions */
                    <BaselineDiagnosticCard
                      questions={diagnosticQuestions}
                      sessionId={session.session_id}
                      topicTitle={session.topic_title}
                      onDiagnosticCompleted={handleDiagnosticCompleted}
                    />
                  ) : action ? (
                    /* Mode 3: Pedagogical Workspaces */
                    <div className="space-y-4">
                      {action.ui_component === "FOUNDATION_BOARD" && (
                        <FoundationBoard
                          payload={action as FoundationBoardPayload}
                          session={session}
                          onUnderstandingChecked={(resp) => {
                            setSession(resp.session);
                            setAction(resp.action);
                            if (resp.prosody_signals) setLastProsodySignals(resp.prosody_signals);
                          }}
                        />
                      )}

                      {action.ui_component === "FADED_EXAMPLE_WORKSPACE" && (
                        <FadedWorkspace
                          payload={action as FadedWorkspacePayload}
                          session={session}
                          onTurnSubmitted={(resp) => {
                            setSession(resp.session);
                            setAction(resp.action);
                            if (resp.evaluation?.feedback) {
                              setLastStudyHabitNudge(resp.evaluation.feedback);
                            }
                            if (resp.evaluation?.prosody_signals) {
                              setLastProsodySignals(resp.evaluation.prosody_signals);
                            }
                          }}
                        />
                      )}

                      {(action.ui_component === "MISCONCEPTION_TRAP" ||
                        action.ui_component === "PROTEGE_VOICE_STAGE") && (
                        <ChallengeStage
                          payload={action as MisconceptionTrapPayload | ProtegeStagePayload}
                          session={session}
                          onTurnSubmitted={(resp) => {
                            setSession(resp.session);
                            setAction(resp.action);
                            if (resp.evaluation?.feedback) {
                              setLastStudyHabitNudge(resp.evaluation.feedback);
                            }
                            if (resp.evaluation?.prosody_signals) {
                              setLastProsodySignals(resp.evaluation.prosody_signals);
                            }
                          }}
                        />
                      )}
                    </div>
                  ) : (
                    <div className="p-8 text-center rounded-2xl border border-dashed border-slate-200 dark:border-zinc-800 text-xs text-slate-500">
                      Loading next pedagogical challenge...
                    </div>
                  )}
                </motion.div>
              </AnimatePresence>
            </div>
          )}
        </main>

        {/* Zone 3: Right Drawer (Live Metacognitive Telemetry) */}
        {session && rightDrawerOpen && (
          <aside className="w-72 lg:w-80 flex-shrink-0 h-[calc(100vh-89px)] border-l border-slate-200 dark:border-zinc-800 animate-in slide-in-from-right duration-200">
            <TelemetryDrawer
              sessionId={session.session_id}
              studyHabitNudge={lastStudyHabitNudge}
              techniqueWeights={session.domain_strategy_weights}
              lastTechniqueUsed={session.last_technique_used}
              prosodySignals={lastProsodySignals}
            />
          </aside>
        )}
      </div>

      {/* Onboarding Modal */}
      <SessionOnboardingModal
        isOpen={isOnboardingOpen}
        onClose={() => setIsOnboardingOpen(false)}
        onSessionInitialized={handleSessionInitialized}
      />

      {/* Adaptive Mini-Exam Modal */}
      {miniExamPayload && session && (
        <MiniExamModal
          exam={miniExamPayload}
          sessionId={session.session_id}
          onClose={() => setMiniExamPayload(null)}
          onExamCompleted={(result: ExamResult) => {
            // Update session state or concept graph with final ratings
            getSessionState(session.session_id).then((fresh) => setSession(fresh));
          }}
        />
      )}
    </div>
  );
}
