"use client";

import React from "react";
import { BookOpen, Sparkles, CheckCircle2, AlertTriangle, ArrowRight, Clock, Award, Calendar, RefreshCw } from "lucide-react";
import { SessionResumeArtifact } from "@/lib/api";

interface SessionResumeCardProps {
  resume: SessionResumeArtifact;
  onRefreshClick?: () => void;
}

export default function SessionResumeCard({
  resume,
  onRefreshClick,
}: SessionResumeCardProps) {
  const isDue = resume.due_for_review;

  const getConqueredList = () => {
    if (!resume.misconceptions_conquered) return [];
    return resume.misconceptions_conquered.map((item) => {
      if (typeof item === "string") {
        return {
          false_belief: item,
          corrected_truth: "Successfully resolved through counter-example testing.",
        };
      }
      return item as { false_belief: string; corrected_truth: string };
    });
  };

  const misconceptions = getConqueredList();

  return (
    <div className="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-md hover:shadow-lg transition-all duration-200 overflow-hidden flex flex-col">
      {/* Top Banner */}
      <div className="px-5 py-4 border-b border-slate-200 dark:border-zinc-800 bg-slate-50/70 dark:bg-zinc-850/40 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
            <BookOpen className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 font-mono">
                {resume.domain.replace("_", " ")}
              </span>
              {isDue && (
                <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/30 flex items-center gap-1">
                  <RefreshCw className="w-3 h-3 animate-spin" />
                  Due for Review
                </span>
              )}
            </div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-zinc-100">
              Session Résumé
            </h3>
          </div>
        </div>

        {/* Spaced Target */}
        <div className="text-right">
          <span className="text-[10px] text-slate-400 dark:text-zinc-500 block">Next Refresher</span>
          <span className="text-xs font-mono font-bold text-indigo-600 dark:text-indigo-400 flex items-center gap-1 justify-end">
            <Calendar className="w-3 h-3" />
            {resume.recommended_refresher_date}
          </span>
        </div>
      </div>

      {/* Body: 3 Structured Columns / Sections */}
      <div className="p-5 space-y-4 flex-1">
        {/* Section 1: Core Mental Model */}
        <div className="space-y-1.5">
          <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800 dark:text-zinc-200">
            <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
            <h4>Core Mental Model</h4>
          </div>
          <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-zinc-850/60 border border-slate-200/80 dark:border-zinc-800 text-xs text-slate-700 dark:text-zinc-300 leading-relaxed whitespace-pre-line font-medium">
            {resume.core_mental_model}
          </div>
        </div>

        {/* Section 2: Winning Analogies */}
        {resume.winning_analogies && resume.winning_analogies.length > 0 && (
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800 dark:text-zinc-200">
              <Award className="w-3.5 h-3.5 text-amber-500" />
              <h4>The Analogy That Clicked</h4>
            </div>
            <div className="space-y-1.5">
              {resume.winning_analogies.map((item: any, idx: number) => (
                <div
                  key={idx}
                  className="p-3 rounded-xl bg-amber-50/50 dark:bg-amber-950/20 border border-amber-500/20 text-xs text-slate-700 dark:text-zinc-300 italic"
                >
                  "{item.analogy || item}"
                  {item.concept && (
                    <span className="not-italic block mt-1 text-[10px] font-mono font-semibold text-amber-700 dark:text-amber-400">
                      Applied to: {item.concept}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Section 3: Conquered Misconceptions */}
        {misconceptions.length > 0 && (
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800 dark:text-zinc-200">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
              <h4>Misconceptions Conquered</h4>
            </div>
            <div className="space-y-2">
              {misconceptions.map((item, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-xl border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-850/40 text-xs space-y-1"
                >
                  <div className="text-[11px] text-rose-600 dark:text-rose-400 line-through">
                    Flawed: {item.false_belief}
                  </div>
                  <div className="text-[11px] font-medium text-emerald-600 dark:text-emerald-400 flex items-start gap-1">
                    <ArrowRight className="w-3 h-3 flex-shrink-0 mt-0.5" />
                    <span>Invariant: {item.corrected_truth}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Metrics Strip Footer */}
      <div className="px-5 py-3 border-t border-slate-200 dark:border-zinc-800 bg-slate-50/70 dark:bg-zinc-850/40 flex items-center justify-between text-xs">
        <div className="flex items-center gap-3">
          <div>
            <span className="text-[10px] text-slate-400 dark:text-zinc-500 block">Mastery Shift</span>
            <span className="font-mono font-bold text-slate-800 dark:text-zinc-200">
              {Math.round(resume.initial_mastery * 100)}% → {Math.round(resume.final_mastery * 100)}%
            </span>
          </div>
          <div className="h-4 w-[1px] bg-slate-200 dark:bg-zinc-700" />
          <div>
            <span className="text-[10px] text-slate-400 dark:text-zinc-500 block">Velocity</span>
            <span className="font-mono font-bold text-indigo-600 dark:text-indigo-400">
              +{(resume.mastery_velocity * 10).toFixed(2)} / 10m
            </span>
          </div>
        </div>

        {resume.most_effective_technique && (
          <span className="font-mono text-[10px] px-2 py-0.5 rounded-full bg-slate-200 dark:bg-zinc-800 text-slate-700 dark:text-zinc-300">
            Best: {resume.most_effective_technique}
          </span>
        )}
      </div>
    </div>
  );
}
