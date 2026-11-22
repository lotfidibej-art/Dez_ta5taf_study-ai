"use client";

import React from "react";
import { AlertCircle, Lightbulb, BookOpen, RefreshCw, Sparkles, X } from "lucide-react";
import { RemediationFeedback } from "@/lib/api";

interface RemediationPanelProps {
  remediation: RemediationFeedback;
  onDismiss?: () => void;
}

export const RemediationPanel: React.FC<RemediationPanelProps> = ({
  remediation,
  onDismiss,
}) => {
  const {
    consecutive_mistakes,
    diagnosis_summary,
    counter_example,
    auto_hint,
    should_backtrack_prerequisite,
  } = remediation;

  return (
    <div className="w-full flex flex-col gap-4 p-5 rounded-2xl bg-white dark:bg-zinc-900 border-2 border-amber-500/40 dark:border-amber-500/40 shadow-xl backdrop-blur-md animate-in fade-in-50 duration-300">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-amber-500/20 pb-3">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/30 flex items-center justify-center text-sm font-bold">
            <AlertCircle className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-amber-600 dark:text-amber-400 uppercase tracking-wider">
                Targeted Mistake Remediation
              </span>
              <span className="px-2 py-0.5 rounded-full text-[11px] font-mono font-bold bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-500/30">
                Attempt #{consecutive_mistakes} • Let&apos;s test your rule
              </span>
            </div>
            <h4 className="text-sm font-semibold text-slate-900 dark:text-zinc-100 tracking-tight mt-0.5">
              Refining Your Mental Model Before Advancing
            </h4>
          </div>
        </div>

        {should_backtrack_prerequisite && (
          <span className="px-2.5 py-1 rounded-lg text-xs font-medium bg-purple-500/10 text-purple-700 dark:text-purple-300 border border-purple-500/30 flex items-center gap-1.5 self-start sm:self-auto">
            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            <span>Prerequisite Backtracking Activated</span>
          </span>
        )}
      </div>

      {/* Diagnosis Summary */}
      <div className="p-3.5 rounded-xl bg-amber-50/60 dark:bg-zinc-850 border border-amber-200/80 dark:border-zinc-800 text-xs text-slate-800 dark:text-zinc-200 leading-relaxed font-sans">
        <span className="text-amber-600 dark:text-amber-400 font-bold block text-[11px] uppercase tracking-wide mb-1">
          What Needs Adjustment:
        </span>
        {diagnosis_summary}
      </div>

      {/* Counter-Example Sandbox Card */}
      {counter_example && (
        <div className="flex flex-col gap-2.5 p-4 rounded-xl bg-slate-50 dark:bg-zinc-950 border border-amber-500/30 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-amber-700 dark:text-amber-400 uppercase tracking-wider flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5" />
              {counter_example.title || "Counter-Example: When Your Rule Breaks"}
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded bg-amber-500/10 text-amber-700 dark:text-amber-300 border border-amber-500/30 font-mono font-semibold">
              Breaking Test Case
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-1 text-xs font-mono">
            {/* Input or Scenario */}
            <div className="p-3 rounded-lg bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 flex flex-col gap-1">
              <span className="text-[10px] text-slate-500 dark:text-zinc-400 uppercase font-sans font-bold">
                Concrete Scenario / Input:
              </span>
              <p className="text-slate-800 dark:text-amber-200 whitespace-pre-wrap leading-relaxed">
                {counter_example.input_or_scenario}
              </p>
            </div>

            {/* Expected vs Student Outcome */}
            <div className="p-3 rounded-lg bg-white dark:bg-zinc-900 border border-rose-500/30 dark:border-rose-500/30 flex flex-col gap-1">
              <span className="text-[10px] text-rose-600 dark:text-rose-400 uppercase font-sans font-bold">
                Student Rule vs. Actual System Behavior:
              </span>
              <p className="text-rose-700 dark:text-rose-300 whitespace-pre-wrap leading-relaxed">
                {counter_example.expected_vs_student_outcome}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Unlocked Auto-Hint & Grounded Source Citation */}
      {auto_hint && (
        <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-zinc-850/80 border border-indigo-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
          <div className="flex items-start gap-2.5">
            <Lightbulb className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
            <div>
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-[11px] font-bold text-indigo-600 dark:text-indigo-400 uppercase font-mono">
                  Auto-Hint (Level {auto_hint.level}/3)
                </span>
              </div>
              <p className="text-slate-800 dark:text-zinc-200 text-xs leading-relaxed font-sans">
                {auto_hint.hint_text}
              </p>
            </div>
          </div>

          {/* Level 2+ Grounded Source Citation Badge */}
          {auto_hint.source_citation && (
            <div className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 border border-indigo-500/30 text-indigo-700 dark:text-indigo-300 text-xs font-medium">
              <BookOpen className="w-3.5 h-3.5" />
              <span>
                {auto_hint.source_citation.file_name} [
                <strong className="font-mono">{auto_hint.source_citation.page_or_timestamp}</strong>]
              </span>
            </div>
          )}
        </div>
      )}

      {/* Guidance */}
      <div className="flex items-center justify-between text-[11px] text-slate-500 dark:text-zinc-400 pt-1">
        <span>
          ✍️ Your previous response has been kept intact below. Modify your logic using the counter-example and retry.
        </span>
        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            className="text-slate-400 hover:text-slate-600 dark:hover:text-zinc-200 underline"
          >
            Dismiss
          </button>
        )}
      </div>
    </div>
  );
};

export default RemediationPanel;
