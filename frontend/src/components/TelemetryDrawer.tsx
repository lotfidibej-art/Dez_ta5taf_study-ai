"use client";

import React, { useState, useEffect } from "react";
import { Lightbulb, Activity, Edit3, ShieldAlert, Zap, Mic, Gauge } from "lucide-react";
import { VoiceProsodySignals } from "@/lib/api";

interface TelemetryDrawerProps {
  studyHabitNudge?: string | null;
  techniqueWeights?: Record<string, number> | null;
  lastTechniqueUsed?: string | null;
  prosodySignals?: VoiceProsodySignals | null;
  sessionId?: string;
}

export default function TelemetryDrawer({
  studyHabitNudge,
  techniqueWeights,
  lastTechniqueUsed,
  prosodySignals,
  sessionId,
}: TelemetryDrawerProps) {
  const [scratchpad, setScratchpad] = useState("");

  useEffect(() => {
    if (sessionId) {
      const saved = localStorage.getItem(`scratchpad_${sessionId}`);
      if (saved) setScratchpad(saved);
    }
  }, [sessionId]);

  const handleScratchpadChange = (val: string) => {
    setScratchpad(val);
    if (sessionId) {
      localStorage.setItem(`scratchpad_${sessionId}`, val);
    }
  };

  const techniques = [
    { key: "faded_example", label: "Faded Practice", color: "bg-indigo-500" },
    { key: "socratic", label: "Socratic Trap", color: "bg-amber-500" },
    { key: "protege", label: "Protégé Voice", color: "bg-emerald-500" },
    { key: "analogy", label: "Conceptual Analogy", color: "bg-purple-500" },
    { key: "visual", label: "Visual Blueprint", color: "bg-sky-500" },
  ];

  return (
    <div className="flex flex-col h-full bg-white dark:bg-zinc-900 border-l border-slate-200 dark:border-zinc-800 transition-colors p-4 space-y-5 overflow-y-auto">
      {/* 1. Metacognitive Study Habit Coach */}
      <div className="rounded-xl border border-indigo-100 dark:border-indigo-950/60 bg-gradient-to-br from-indigo-50/70 to-purple-50/40 dark:from-indigo-950/20 dark:to-zinc-900 p-3.5 shadow-2xs">
        <div className="flex items-center gap-2 text-indigo-700 dark:text-indigo-400 font-semibold text-xs mb-1.5">
          <Lightbulb className="w-4 h-4 text-amber-500 dark:text-amber-400" />
          <span>Study Habit Coach</span>
        </div>
        <p className="text-xs text-slate-700 dark:text-zinc-300 leading-relaxed">
          {studyHabitNudge ||
            "Articulate the causal 'why' behind each rule. Generating self-explanations out loud anchors deep invariant retention."}
        </p>
      </div>

      {/* 2. Prosody & Cognitive Telemetry (when voice used) */}
      {prosodySignals && (
        <div className="rounded-xl border border-slate-200 dark:border-zinc-800 bg-slate-50/60 dark:bg-zinc-800/20 p-3.5 space-y-2.5">
          <div className="flex items-center justify-between text-xs font-semibold text-slate-900 dark:text-zinc-100">
            <span className="flex items-center gap-1.5">
              <Mic className="w-3.5 h-3.5 text-indigo-500" />
              Voice Prosody Engine
            </span>
            <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-slate-200 dark:bg-zinc-800">
              Local Whisper
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2 text-[11px]">
            <div className="p-2 rounded-lg bg-white dark:bg-zinc-850 border border-slate-200/60 dark:border-zinc-700/40">
              <span className="text-[10px] text-slate-500 dark:text-zinc-400 block">Speech Rate</span>
              <span className="font-mono font-bold text-slate-800 dark:text-zinc-200">
                {Math.round(prosodySignals.speech_rate_wpm || 0)} WPM
              </span>
            </div>
            <div className="p-2 rounded-lg bg-white dark:bg-zinc-850 border border-slate-200/60 dark:border-zinc-700/40">
              <span className="text-[10px] text-slate-500 dark:text-zinc-400 block">Pause Gaps</span>
              <span className="font-mono font-bold text-slate-800 dark:text-zinc-200">
                {prosodySignals.hesitation_pause_count ?? 0} ({prosodySignals.max_pause_sec?.toFixed(1) ?? "0"}s)
              </span>
            </div>
          </div>

          {prosodySignals.monotone_recitation_flag && (
            <div className="flex items-start gap-1.5 p-2 rounded-lg bg-amber-500/10 border border-amber-500/30 text-[11px] text-amber-700 dark:text-amber-400">
              <ShieldAlert className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
              <span>Rushed verbatim recitation detected. Deep causal reasoning required.</span>
            </div>
          )}

          {prosodySignals.fluency_signal && (
            <div className="text-[10px] text-emerald-600 dark:text-emerald-400 font-medium">
              Signal: {prosodySignals.fluency_signal}
            </div>
          )}
        </div>
      )}

      {/* 3. Multi-Armed Bandit Technique Weights */}
      <div className="space-y-3">
        <div className="flex items-center justify-between text-xs font-semibold text-slate-900 dark:text-zinc-100">
          <span className="flex items-center gap-1.5">
            <Activity className="w-3.5 h-3.5 text-purple-500" />
            Adaptive Bandit Weights
          </span>
          <span className="text-[10px] text-slate-500 dark:text-zinc-400 font-mono">Real-time</span>
        </div>

        <div className="space-y-2">
          {techniques.map((t) => {
            const rawWeight = techniqueWeights?.[t.key] ?? 1.0;
            const pct = Math.min(100, Math.round((rawWeight / 1.0) * 100));
            const isLastUsed = lastTechniqueUsed?.toLowerCase().includes(t.key);

            return (
              <div key={t.key} className="space-y-1">
                <div className="flex items-center justify-between text-[11px]">
                  <span
                    className={`font-medium ${
                      isLastUsed
                        ? "text-indigo-600 dark:text-indigo-400 font-bold"
                        : "text-slate-600 dark:text-zinc-400"
                    }`}
                  >
                    {t.label}
                    {isLastUsed && " • Active"}
                  </span>
                  <span className="font-mono text-[10px] text-slate-500 dark:text-zinc-400">
                    {(rawWeight).toFixed(2)}
                  </span>
                </div>
                <div className="h-1.5 w-full bg-slate-100 dark:bg-zinc-800 rounded-full overflow-hidden">
                  <div
                    className={`h-full ${t.color} rounded-full transition-all duration-500`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 4. Session Scratchpad */}
      <div className="flex-1 flex flex-col min-h-[160px] space-y-2">
        <div className="flex items-center justify-between text-xs font-semibold text-slate-900 dark:text-zinc-100">
          <span className="flex items-center gap-1.5">
            <Edit3 className="w-3.5 h-3.5 text-slate-500" />
            Session Scratchpad
          </span>
          <span className="text-[10px] text-slate-400 dark:text-zinc-500 font-mono">Auto-saved</span>
        </div>
        <textarea
          value={scratchpad}
          onChange={(e) => handleScratchpadChange(e.target.value)}
          placeholder="Jot down formulas, code traces, or mental model notes here..."
          className="flex-1 w-full resize-none rounded-xl border border-slate-200 dark:border-zinc-800 bg-slate-50/70 dark:bg-zinc-850/60 p-3 text-xs font-mono text-slate-800 dark:text-zinc-200 placeholder:text-slate-400 focus:outline-hidden focus:ring-1 focus:ring-indigo-500 transition-all leading-relaxed"
        />
      </div>
    </div>
  );
}
