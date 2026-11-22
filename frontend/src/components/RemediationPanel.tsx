"use client";

import React from "react";
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
    <div className="w-full flex flex-col gap-4 p-5 rounded-2xl bg-gradient-to-r from-rose-950/40 via-neutral-900 to-amber-950/30 border border-rose-500/30 shadow-2xl backdrop-blur-md animate-in fade-in-50 duration-300">
      {/* Block 1: Header & What Needs Adjustment */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-rose-500/20 pb-3">
        <div className="flex items-center gap-2.5">
          <span className="w-8 h-8 rounded-xl bg-rose-500/20 text-rose-400 border border-rose-500/30 flex items-center justify-center text-sm font-bold">
            ⚡
          </span>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-rose-400 uppercase tracking-wider">
                Targeted Mistake Remediation
              </span>
              <span className="px-2 py-0.5 rounded-full text-[11px] font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                Attempt #{consecutive_mistakes} • Let&apos;s test your rule
              </span>
            </div>
            <h4 className="text-sm font-semibold text-white tracking-tight mt-0.5">
              Refining Your Mental Model Before Advancing
            </h4>
          </div>
        </div>

        {should_backtrack_prerequisite && (
          <span className="px-2.5 py-1 rounded-lg text-xs font-medium bg-purple-500/20 text-purple-300 border border-purple-500/40 flex items-center gap-1.5 self-start sm:self-auto">
            <span>🔄</span> Prerequisite Backtracking Activated
          </span>
        )}
      </div>

      {/* Diagnosis Summary */}
      <div className="p-3.5 rounded-xl bg-neutral-950/70 border border-neutral-800 text-xs md:text-sm text-neutral-200 leading-relaxed font-sans">
        <span className="text-rose-400 font-bold block text-[11px] uppercase tracking-wide mb-1">
          What Needs Adjustment:
        </span>
        {diagnosis_summary}
      </div>

      {/* Block 2: Counter-Example Sandbox Card */}
      {counter_example && (
        <div className="flex flex-col gap-2.5 p-4 rounded-xl bg-neutral-950 border border-amber-500/30 shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-amber-400 uppercase tracking-wider flex items-center gap-1.5">
              <span>🔬</span> {counter_example.title || "Counter-Example: When Your Rule Breaks"}
            </span>
            <span className="text-[11px] px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20 font-mono">
              Breaking Test Case
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-1 text-xs font-mono">
            {/* Input or Scenario */}
            <div className="p-3 rounded-lg bg-neutral-900 border border-neutral-800 flex flex-col gap-1">
              <span className="text-[10px] text-neutral-500 uppercase font-sans font-bold">
                Concrete Scenario / Input:
              </span>
              <p className="text-amber-200 whitespace-pre-wrap leading-relaxed">
                {counter_example.input_or_scenario}
              </p>
            </div>

            {/* Expected vs Student Outcome */}
            <div className="p-3 rounded-lg bg-neutral-900 border border-neutral-800 flex flex-col gap-1">
              <span className="text-[10px] text-rose-400 uppercase font-sans font-bold">
                Student Rule vs. Actual System Behavior:
              </span>
              <p className="text-rose-200 whitespace-pre-wrap leading-relaxed">
                {counter_example.expected_vs_student_outcome}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Block 3: Unlocked Auto-Hint & Grounded Source Citation */}
      {auto_hint && (
        <div className="p-3.5 rounded-xl bg-neutral-900/90 border border-purple-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
          <div className="flex items-start gap-2.5">
            <span className="text-amber-400 text-base shrink-0 mt-0.5">💡</span>
            <div>
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-[11px] font-bold text-amber-300 uppercase">
                  Auto-Hint (Level {auto_hint.level}/3)
                </span>
              </div>
              <p className="text-neutral-200 text-xs md:text-sm font-sans leading-relaxed">
                {auto_hint.hint_text}
              </p>
            </div>
          </div>

          {/* Level 2+ Grounded Source Citation Badge */}
          {auto_hint.source_citation && (
            <div className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-500/15 border border-indigo-500/30 text-indigo-200 text-xs font-medium">
              <span>📖</span>
              <span>
                {auto_hint.source_citation.file_name} [
                <strong>{auto_hint.source_citation.page_or_timestamp}</strong>]
              </span>
            </div>
          )}
        </div>
      )}

      {/* Footer / Guidance */}
      <div className="flex items-center justify-between text-[11px] text-neutral-400 pt-1">
        <span>
          ✍️ Your previous response has been kept below. Modify your logic using the counter-example and retry.
        </span>
        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            className="text-neutral-500 hover:text-neutral-300 underline"
          >
            Dismiss
          </button>
        )}
      </div>
    </div>
  );
};
