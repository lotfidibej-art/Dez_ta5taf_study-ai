"use client";

import React, { useState } from "react";
import {
  FadedWorkspacePayload,
  SessionState,
  SubmitTurnResponse,
  requestHint,
  submitTurn,
} from "@/lib/api";
import { RemediationPanel } from "@/components/RemediationPanel";

interface FadedWorkspaceProps {
  payload: FadedWorkspacePayload;
  session: SessionState;
  onTurnSubmitted?: (response: SubmitTurnResponse) => void;
}

export const FadedWorkspace: React.FC<FadedWorkspaceProps> = ({
  payload,
  session,
  onTurnSubmitted,
}) => {
  const [stepAnswers, setStepAnswers] = useState<Record<string, string>>({});
  const [overallExplanation, setOverallExplanation] = useState<string>("");
  const [currentHint, setCurrentHint] = useState<Record<string, unknown> | null>(
    payload.active_hint || null
  );
  const [hintLevel, setHintLevel] = useState<number>(session.current_hint_level ?? 0);
  const [isLoadingHint, setIsLoadingHint] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [lastFeedback, setLastFeedback] = useState<SubmitTurnResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const activeNode = (session.concept_graph ?? []).find(
    (n) => n.concept_id === session.active_concept_id
  );
  const conceptTitle = activeNode ? activeNode.title : session.topic_title;
  const activeRemediation = lastFeedback?.remediation || session.active_remediation;

  const handleStepAnswerChange = (stepNumber: number, val: string) => {
    setStepAnswers((prev) => ({
      ...prev,
      [String(stepNumber)]: val,
    }));
  };

  const handleRequestHint = async () => {
    if (hintLevel >= 3) return;
    setIsLoadingHint(true);
    setErrorMessage(null);

    try {
      const resp = await requestHint(session.session_id);
      setCurrentHint(resp.active_hint);
      setHintLevel(resp.hint_level);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMessage(msg);
    } finally {
      setIsLoadingHint(false);
    }
  };

  const handleSubmitSolution = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const resp = await submitTurn(session.session_id, {
        text_input: overallExplanation || Object.values(stepAnswers).join("\n"),
        step_answers: stepAnswers,
        response_latency_sec: 15.0,
      });

      setLastFeedback(resp);
      if (onTurnSubmitted) {
        onTurnSubmitted(resp);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 w-full max-w-5xl mx-auto">
      {/* Top Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-neutral-900/80 border border-amber-500/20 shadow-xl backdrop-blur-sm">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
              Tier 2 • Faded Example Workspace
            </span>
            <span className="text-neutral-500 text-xs">Guided Practice (40% - 75% Mastery)</span>
          </div>
          <h2 className="text-xl md:text-2xl font-bold text-white tracking-tight">
            {conceptTitle}
          </h2>
        </div>

        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className="text-xs text-neutral-400">Current Concept Mastery</div>
            <div className="text-lg font-bold text-amber-400">
              {Math.round((activeNode?.mastery_rating ?? 0) * 100)}%
            </div>
          </div>

          {/* Hint Trigger Button */}
          <button
            type="button"
            onClick={handleRequestHint}
            disabled={isLoadingHint || hintLevel >= 3}
            className={`px-3.5 py-2 rounded-xl text-xs font-semibold border flex items-center gap-2 transition-all ${
              hintLevel >= 3
                ? "bg-neutral-800 text-neutral-500 border-neutral-700 cursor-not-allowed"
                : "bg-amber-500/10 text-amber-300 border-amber-500/30 hover:bg-amber-500/20 shadow-sm"
            }`}
          >
            <span>💡</span>
            <span>
              {hintLevel >= 3
                ? "Max Hints Reached (3/3)"
                : `Need a Hint? (${hintLevel}/3)`}
            </span>
          </button>
        </div>
      </div>

      {/* Contingent Hint Banner (Progressive Scaffold) */}
      {currentHint && (
        <div className="p-4 rounded-xl bg-gradient-to-r from-amber-950/40 to-neutral-900 border border-amber-500/30 shadow-md flex flex-col gap-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                Hint Level {String(currentHint.level || hintLevel)} • {String(currentHint.hint_type || "NUDGE")}
              </span>
              {currentHint.hint_penalty !== undefined && (
                <span className="text-xs text-neutral-400">
                  (-0.03 score penalty applied)
                </span>
              )}
            </div>

            {/* Level 2+ Source Citation Badge */}
            {Boolean(currentHint.source_citation) && (
              <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-500/15 text-indigo-300 border border-indigo-500/30 flex items-center gap-1.5">
                <span>📖</span>
                <span>
                  Source:{" "}
                  <strong>
                    {String(
                      (currentHint.source_citation as { file_name?: string })?.file_name || "Document"
                    )}
                  </strong>{" "}
                  [
                  {String(
                    (currentHint.source_citation as { page_or_timestamp?: string })?.page_or_timestamp || "Location"
                  )}
                  ]
                </span>
              </span>
            )}
          </div>

          <p className="text-sm text-neutral-200 leading-relaxed font-sans">
            {String(currentHint.hint_text || "")}
          </p>

          {/* Level 3 Structural Skeleton */}
          {Boolean(currentHint.skeleton_template) && (
            <pre className="p-3 rounded-lg bg-neutral-950 border border-neutral-800 text-amber-300 font-mono text-xs overflow-x-auto">
              {String(currentHint.skeleton_template)}
            </pre>
          )}
        </div>
      )}

      {/* Targeted Mistake Remediation Panel (Slice 6) */}
      {activeRemediation && (
        <RemediationPanel remediation={activeRemediation} />
      )}

      {/* Problem Statement Card */}
      <div className="p-5 rounded-2xl bg-neutral-900/60 border border-neutral-800 shadow-md">
        <span className="text-xs font-bold text-neutral-400 uppercase tracking-wider block mb-1">
          Challenge Goal:
        </span>
        <p className="text-sm md:text-base font-medium text-white leading-relaxed">
          {payload.problem_statement}
        </p>
      </div>

      {/* Step Sequence Workspace */}
      <form onSubmit={handleSubmitSolution} className="flex flex-col gap-4">
        <div className="space-y-4">
          {payload.steps.map((step, idx) => {
            const stepNum = Number(step.step_number ?? idx + 1);
            const isFaded = Boolean(step.is_faded || step.step_type === "FADED");

            return (
              <div
                key={idx}
                className={`p-5 rounded-2xl border transition-all ${
                  isFaded
                    ? "bg-amber-950/15 border-amber-500/30 shadow-md"
                    : "bg-neutral-900/50 border-neutral-800"
                }`}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <span
                      className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                        isFaded
                          ? "bg-amber-500 text-black"
                          : "bg-neutral-800 text-neutral-300"
                      }`}
                    >
                      {stepNum}
                    </span>
                    <span className="text-sm md:text-base font-semibold text-white">
                      {String(step.label || `Step ${stepNum}`)}
                    </span>
                  </div>

                  <span
                    className={`text-xs px-2.5 py-0.5 rounded-full font-mono ${
                      isFaded
                        ? "bg-amber-500/20 text-amber-300 border border-amber-500/30 font-semibold"
                        : "bg-neutral-800 text-neutral-400"
                    }`}
                  >
                    {isFaded ? "FADED • COMPLETE THIS" : "WORKED DEMONSTRATION"}
                  </span>
                </div>

                {/* Demonstration Code or Student Blank */}
                {!isFaded ? (
                  <pre className="p-3.5 rounded-xl bg-neutral-950 border border-neutral-800/80 text-emerald-400 font-mono text-xs md:text-sm overflow-x-auto">
                    {String(step.code || "")}
                  </pre>
                ) : (
                  <div className="space-y-2 mt-2">
                    <pre className="p-3.5 rounded-xl bg-neutral-950 border border-neutral-800/80 text-amber-300 font-mono text-xs md:text-sm overflow-x-auto">
                      {String(step.code || "return _______")}
                    </pre>
                    <input
                      type="text"
                      placeholder="Fill in the blank value or expression..."
                      value={stepAnswers[String(stepNum)] || ""}
                      onChange={(e) => handleStepAnswerChange(stepNum, e.target.value)}
                      className="w-full px-4 py-2.5 text-xs md:text-sm rounded-xl bg-neutral-950 border border-neutral-800 text-white placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-amber-500 font-mono"
                    />
                  </div>
                )}

                {/* Step Annotation */}
                {Boolean(step.annotation) && (
                  <p className="text-xs text-neutral-400 mt-2.5 leading-relaxed italic">
                    💡 {String(step.annotation)}
                  </p>
                )}
              </div>
            );
          })}
        </div>

        {/* Conceptual Justification Input */}
        <div className="p-5 rounded-2xl bg-neutral-900/60 border border-neutral-800 flex flex-col gap-2 mt-2">
          <label className="text-xs font-semibold text-neutral-300 uppercase tracking-wide">
            Causal Explanation (Why does this sequence solve the problem?):
          </label>
          <textarea
            value={overallExplanation}
            onChange={(e) => setOverallExplanation(e.target.value)}
            placeholder="Explain the causal mechanics connecting the worked steps to your completed faded blanks..."
            rows={2}
            className="w-full rounded-xl bg-neutral-950 border border-neutral-800 px-4 py-2.5 text-xs md:text-sm text-neutral-100 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-amber-500"
          />
        </div>

        {/* Submission Action Bar */}
        <div className="flex items-center justify-between gap-4 mt-2">
          {errorMessage && (
            <span className="text-xs text-rose-400 font-medium">⚠️ {errorMessage}</span>
          )}
          {!errorMessage && (
            <span className="text-xs text-neutral-500">
              Evaluated on correctness and depth. Scores &ge; 75% unlock Mastery Traps.
            </span>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className="px-6 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-black font-bold text-xs md:text-sm shadow-lg shadow-amber-500/20 transition-all disabled:opacity-50"
          >
            {isSubmitting ? "Evaluating Solution..." : "Submit Solution & Advance"}
          </button>
        </div>
      </form>

      {/* Post-Turn Feedback Banner */}
      {lastFeedback && (
        <div className="p-4 rounded-xl bg-neutral-900 border border-neutral-700 text-white flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-emerald-400 uppercase">
              Evaluation Result
            </span>
            <span className="text-xs text-neutral-400">
              Updated Mastery: {Math.round(lastFeedback.updated_mastery_rating * 100)}%
            </span>
          </div>
          <p className="text-xs text-neutral-300">{lastFeedback.evaluation.feedback}</p>
        </div>
      )}
    </div>
  );
};
