"use client";

import React, { useState } from "react";
import {
  FoundationBoardPayload,
  SessionState,
  UnderstandingCheckResponse,
  checkUnderstanding,
} from "@/lib/api";
import { MermaidDiagram } from "@/components/MermaidDiagram";

interface FoundationBoardProps {
  payload: FoundationBoardPayload;
  session: SessionState;
  onUnderstandingChecked?: (response: UnderstandingCheckResponse) => void;
}

export const FoundationBoard: React.FC<FoundationBoardProps> = ({
  payload,
  session,
  onUnderstandingChecked,
}) => {
  const [activeTab, setActiveTab] = useState<"diagram" | "lab">("diagram");
  const [isNudgeDismissed, setIsNudgeDismissed] = useState<boolean>(false);
  const [reflectionText, setReflectionText] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [submissionFeedback, setSubmissionFeedback] = useState<UnderstandingCheckResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const activeNode = (session.concept_graph ?? []).find((n) => n.concept_id === payload.concept_id);
  const conceptTitle = activeNode ? activeNode.title : session.topic_title;

  const handleCheckUnderstanding = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reflectionText.trim()) return;

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const resp = await checkUnderstanding(session.session_id, {
        student_response: reflectionText.trim(),
        concept_id: payload.concept_id,
      });
      setSubmissionFeedback(resp);
      if (onUnderstandingChecked) {
        onUnderstandingChecked(resp);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 w-full max-w-7xl mx-auto">
      {/* Top Banner / Concept Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-neutral-900/80 border border-neutral-800 shadow-xl backdrop-blur-sm">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              Tier 1 • Foundation Board
            </span>
            <span className="text-neutral-500 text-xs">Comprehension &lt; 40%</span>
          </div>
          <h2 className="text-xl md:text-2xl font-bold text-white tracking-tight">
            {conceptTitle}
          </h2>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-right">
            <div className="text-xs text-neutral-400">Current Concept Mastery</div>
            <div className="text-lg font-bold text-emerald-400">
              {Math.round((activeNode?.mastery_rating ?? 0) * 100)}%
            </div>
          </div>
          <div className="w-16 h-2 bg-neutral-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-emerald-500 rounded-full transition-all duration-500"
              style={{ width: `${Math.min(100, Math.round((activeNode?.mastery_rating ?? 0) * 100))}%` }}
            />
          </div>
        </div>
      </div>

      {/* Dismissible Metacognitive Study Nudge Banner */}
      {payload.study_habit_nudge && !isNudgeDismissed && (
        <div className="relative flex items-start justify-between gap-3 p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-200">
          <div className="flex items-start gap-3">
            <span className="text-lg">💡</span>
            <div>
              <div className="font-semibold text-xs tracking-wider uppercase text-amber-400">
                Study Coach Metacognitive Nudge
              </div>
              <p className="text-sm text-neutral-200 mt-0.5 leading-relaxed">
                {payload.study_habit_nudge}
              </p>
            </div>
          </div>
          <button
            onClick={() => setIsNudgeDismissed(true)}
            className="text-neutral-400 hover:text-white text-xs px-2 py-1 rounded-md bg-neutral-800/50 hover:bg-neutral-800 transition-colors"
            title="Dismiss nudge"
          >
            ✕
          </button>
        </div>
      )}

      {/* Main Split-Pane Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Pane: Bullets Breakdown & Bridge Analogy */}
        <div className="lg:col-span-5 flex flex-col gap-5">
          {/* Bullet Points Breakdown */}
          <div className="p-6 rounded-2xl bg-neutral-900/60 border border-neutral-800 shadow-md flex flex-col gap-4">
            <div className="flex items-center gap-2">
              <span className="p-1.5 rounded-lg bg-neutral-800 text-indigo-400 text-sm">🎯</span>
              <h3 className="font-semibold text-white text-sm uppercase tracking-wide">
                Core Mental Model
              </h3>
            </div>
            <ul className="space-y-3">
              {payload.bullet_breakdown.map((bullet, idx) => (
                <li key={idx} className="flex items-start gap-3 text-sm text-neutral-300 leading-relaxed">
                  <span className="mt-1 h-2 w-2 rounded-full bg-indigo-500 shrink-0" />
                  <span>{bullet}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Bridge Analogy Card */}
          {payload.bridge_analogy && (
            <div className="p-6 rounded-2xl bg-gradient-to-br from-indigo-950/30 to-purple-950/20 border border-indigo-500/20 shadow-md flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-indigo-400">🌉</span>
                  <h3 className="font-semibold text-white text-sm">Bridge Analogy</h3>
                </div>
                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                  Connected from your memory
                </span>
              </div>

              <div className="text-xs text-neutral-400 flex items-center gap-2">
                <span className="font-medium text-neutral-200">
                  {payload.bridge_analogy.source_concept || payload.bridge_analogy.source}
                </span>
                <span>➔</span>
                <span className="font-medium text-indigo-300">
                  {payload.bridge_analogy.target_concept || payload.bridge_analogy.target}
                </span>
              </div>

              <p className="text-sm text-neutral-300 leading-relaxed bg-neutral-900/60 p-3.5 rounded-xl border border-neutral-800/80">
                {payload.bridge_analogy.mapping}
              </p>
            </div>
          )}
        </div>

        {/* Right Pane: Tabbed View (Mermaid Visual vs Interactive Lab) */}
        <div className="lg:col-span-7 flex flex-col gap-4">
          <div className="p-6 rounded-2xl bg-neutral-900/60 border border-neutral-800 shadow-md flex flex-col gap-4 min-h-[460px]">
            {/* Tab Selector */}
            <div className="flex items-center justify-between border-b border-neutral-800 pb-3">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setActiveTab("diagram")}
                  className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all flex items-center gap-2 ${
                    activeTab === "diagram"
                      ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/30"
                      : "bg-neutral-800/60 text-neutral-400 hover:text-white"
                  }`}
                >
                  <span>📊</span> Concept Visual Diagram
                </button>

                {payload.interactive_lab && (
                  <button
                    onClick={() => setActiveTab("lab")}
                    className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all flex items-center gap-2 ${
                      activeTab === "lab"
                        ? "bg-emerald-600 text-white shadow-lg shadow-emerald-600/30"
                        : "bg-neutral-800/60 text-neutral-400 hover:text-white"
                    }`}
                  >
                    <span>🧪</span> Interactive Lab Sandbox
                  </button>
                )}
              </div>

              {activeTab === "lab" && payload.interactive_lab && (
                <span className="text-xs text-neutral-400 font-mono hidden sm:inline">
                  {payload.interactive_lab.platform}
                </span>
              )}
            </div>

            {/* Tab 1: Mermaid Diagram */}
            {activeTab === "diagram" && (
              <div className="flex-1 flex flex-col justify-center">
                {payload.mermaid_diagram ? (
                  <MermaidDiagram chart={payload.mermaid_diagram} />
                ) : (
                  <div className="text-center text-sm text-neutral-500 py-16">
                    No structural diagram available for this concept.
                  </div>
                )}
              </div>
            )}

            {/* Tab 2: Interactive Lab Sandbox */}
            {activeTab === "lab" && payload.interactive_lab && (
              <div className="flex-1 flex flex-col gap-3">
                {/* Pinned Experiment Goal Instruction */}
                <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-200 text-xs flex items-center gap-2.5">
                  <span className="text-base shrink-0">🔬</span>
                  <div>
                    <span className="font-semibold text-emerald-400 uppercase tracking-wider text-[10px] block">
                      Target Experiment Goal
                    </span>
                    <span className="text-neutral-200">
                      {payload.interactive_lab.instruction}
                    </span>
                  </div>
                </div>

                {/* Sandboxed iframe */}
                <div className="relative w-full h-[400px] md:h-[480px] rounded-xl overflow-hidden border border-neutral-800 bg-black">
                  <iframe
                    src={payload.interactive_lab.lab_url}
                    title={payload.interactive_lab.title || "Interactive Lab Sandbox"}
                    className="w-full h-full border-0"
                    sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
                    loading="lazy"
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Bottom Action Bar: Check Understanding */}
      <div className="p-6 rounded-2xl bg-neutral-900/80 border border-neutral-800 shadow-xl flex flex-col gap-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <span>✍️</span> Check My Understanding
            </h3>
            <p className="text-xs text-neutral-400 mt-0.5">
              Explain this concept back in your own words, or describe what you observed in the visual diagram/lab.
            </p>
          </div>
          <span className="text-xs text-neutral-500">
            Target to advance: &ge; 40% mastery
          </span>
        </div>

        <form onSubmit={handleCheckUnderstanding} className="flex flex-col gap-3">
          <textarea
            value={reflectionText}
            onChange={(e) => setReflectionText(e.target.value)}
            placeholder="In my own words, the mechanism works because..."
            rows={3}
            className="w-full rounded-xl bg-neutral-950 border border-neutral-800 px-4 py-3 text-sm text-neutral-100 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
            disabled={isSubmitting}
          />

          <div className="flex items-center justify-between">
            {errorMessage ? (
              <span className="text-xs text-rose-400 font-medium">⚠️ {errorMessage}</span>
            ) : (
              <span className="text-xs text-neutral-500">
                Evaluated by Agent 3 on factual correctness and causal depth.
              </span>
            )}

            <button
              type="submit"
              disabled={isSubmitting || !reflectionText.trim()}
              className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-semibold text-xs transition-all shadow-lg shadow-indigo-600/20 flex items-center gap-2"
            >
              {isSubmitting ? (
                <>
                  <span className="animate-spin text-sm">⏳</span> Evaluating...
                </>
              ) : (
                <>
                  <span>Submit & Advance</span> ➔
                </>
              )}
            </button>
          </div>
        </form>

        {/* Feedback Display */}
        {submissionFeedback && (
          <div
            className={`p-4 rounded-xl border mt-2 flex flex-col gap-2 ${
              submissionFeedback.advanced_tier
                ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-200"
                : "bg-indigo-500/10 border-indigo-500/30 text-indigo-200"
            }`}
          >
            <div className="flex items-center justify-between text-xs font-semibold">
              <span>
                {submissionFeedback.advanced_tier
                  ? "🎉 Mastery Goal Reached! Ready for Guided Practice (Tier 2)"
                  : "📌 Understanding Check Evaluated"}
              </span>
              <span className="px-2 py-0.5 rounded bg-black/40">
                Updated Score: {Math.round(submissionFeedback.updated_mastery_rating * 100)}%
              </span>
            </div>
            <p className="text-xs text-neutral-200 leading-relaxed">
              {submissionFeedback.feedback}
            </p>
            {submissionFeedback.identified_misconception && (
              <div className="text-[11px] text-amber-300 font-mono bg-amber-500/10 px-2 py-1 rounded">
                Note detected misconception: {submissionFeedback.identified_misconception}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
