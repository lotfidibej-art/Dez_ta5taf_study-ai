"use client";

import React, { useState } from "react";
import {
  MisconceptionTrapPayload,
  ProtegeStagePayload,
  SessionState,
  SubmitTurnResponse,
  submitTurn,
  submitTurnVoice,
} from "@/lib/api";
import { VoiceRecorder } from "@/components/VoiceRecorder";
import { RemediationPanel } from "@/components/RemediationPanel";

interface ChallengeStageProps {
  payload: MisconceptionTrapPayload | ProtegeStagePayload;
  session: SessionState;
  onTurnSubmitted?: (response: SubmitTurnResponse) => void;
}

export const ChallengeStage: React.FC<ChallengeStageProps> = ({
  payload,
  session,
  onTurnSubmitted,
}) => {
  const [responseInput, setResponseInput] = useState<string>("");
  const [useVoiceInput, setUseVoiceInput] = useState<boolean>(
    payload.ui_component === "PROTEGE_VOICE_STAGE" &&
      Boolean((payload as ProtegeStagePayload).require_voice_input ?? true)
  );
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [lastFeedback, setLastFeedback] = useState<SubmitTurnResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const isTrap = payload.ui_component === "MISCONCEPTION_TRAP";
  const activeNode = (session.concept_graph ?? []).find(
    (n) => n.concept_id === session.active_concept_id
  );
  const conceptTitle = activeNode ? activeNode.title : session.topic_title;
  const activeRemediation = lastFeedback?.remediation || session.active_remediation;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!responseInput.trim()) return;

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const resp = await submitTurn(session.session_id, {
        text_input: responseInput.trim(),
        response_latency_sec: 20.0,
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

  const handleVoiceSubmit = async (audioBlob: Blob) => {
    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const resp = await submitTurnVoice(session.session_id, audioBlob, {
        responseLatencySec: 20.0,
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
      <div
        className={`flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl shadow-xl backdrop-blur-sm border ${
          isTrap
            ? "bg-rose-950/20 border-rose-500/20"
            : "bg-purple-950/20 border-purple-500/20"
        }`}
      >
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span
              className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${
                isTrap
                  ? "bg-rose-500/10 text-rose-400 border-rose-500/20"
                  : "bg-purple-500/10 text-purple-300 border-purple-500/20"
              }`}
            >
              Tier 3 • {isTrap ? "Adversarial Misconception Trap" : `Protégé Teaching Mode (Turn ${session.protege_turn_count + 1})`}
            </span>
            <span className="text-neutral-500 text-xs">Deep Mastery Challenge (&gt; 75%)</span>
          </div>
          <h2 className="text-xl md:text-2xl font-bold text-white tracking-tight">
            {conceptTitle}
          </h2>
        </div>

        <div className="text-right">
          <div className="text-xs text-neutral-400">Current Concept Mastery</div>
          <div
            className={`text-lg font-bold ${
              isTrap ? "text-rose-400" : "text-purple-300"
            }`}
          >
            {Math.round((activeNode?.mastery_rating ?? 0) * 100)}%
          </div>
        </div>
      </div>

      {/* Targeted Mistake Remediation Panel (Slice 6) */}
      {activeRemediation && (
        <RemediationPanel remediation={activeRemediation} />
      )}

      {/* Challenge Body */}
      {isTrap ? (
        /* MODE A: MISCONCEPTION TRAP */
        <div className="space-y-4">
          <div className="p-5 rounded-2xl bg-neutral-900/60 border border-neutral-800 shadow-md">
            <span className="text-xs font-bold text-rose-400 uppercase tracking-wider block mb-1">
              Scenario / Peer Proposal:
            </span>
            <p className="text-sm md:text-base text-neutral-200 leading-relaxed">
              {(payload as MisconceptionTrapPayload).scenario_intro}
            </p>
          </div>

          <div className="p-5 rounded-2xl bg-neutral-950 border border-neutral-800 shadow-lg">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-mono uppercase tracking-wider text-neutral-500">
                Flawed Artifact [{(payload as MisconceptionTrapPayload).artifact_language || "code"}]
              </span>
              <span className="text-xs text-rose-400 font-semibold">
                ⚠️ Contains 1 subtle conceptual fallacy
              </span>
            </div>
            <pre className="p-4 rounded-xl bg-neutral-900 border border-neutral-800/80 text-rose-300 font-mono text-xs md:text-sm overflow-x-auto">
              {(payload as MisconceptionTrapPayload).flawed_artifact}
            </pre>
          </div>
        </div>
      ) : (
        /* MODE B: PROTÉGÉ TEACHING STAGE */
        <div className="space-y-4">
          <div className="p-6 rounded-2xl bg-gradient-to-r from-purple-950/30 to-neutral-900/60 border border-purple-500/20 shadow-md flex items-start gap-4">
            <div className="w-12 h-12 rounded-2xl bg-purple-500/20 border border-purple-500/30 flex items-center justify-center text-2xl shrink-0">
              🤖
            </div>
            <div className="space-y-1">
              <span className="text-xs font-bold text-purple-300 uppercase tracking-wider">
                Curious Peer Learner Asks (Turn {session.protege_turn_count + 1}):
              </span>
              <p className="text-base font-medium text-white leading-relaxed">
                {(payload as ProtegeStagePayload).ai_persona_question}
              </p>
            </div>
          </div>

          {Boolean((payload as ProtegeStagePayload).target_explanation_points?.length) && (
            <div className="p-5 rounded-2xl bg-neutral-900/60 border border-neutral-800">
              <span className="text-xs font-bold text-neutral-400 uppercase tracking-wider block mb-2">
                Essential Points to Cover in Your Spoken Explanation:
              </span>
              <ul className="space-y-2">
                {(payload as ProtegeStagePayload).target_explanation_points.map((pt, idx) => (
                  <li key={idx} className="flex items-start gap-2.5 text-xs md:text-sm text-neutral-300">
                    <span className="w-4 h-4 rounded-full bg-purple-500/20 text-purple-300 flex items-center justify-center shrink-0 mt-0.5 text-[10px] font-bold">
                      ✓
                    </span>
                    <span>{pt}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Toggle between Voice and Text Input */}
          <div className="flex justify-end">
            <button
              type="button"
              onClick={() => setUseVoiceInput(!useVoiceInput)}
              className="text-xs text-purple-400 hover:text-purple-300 underline font-medium flex items-center gap-1.5"
            >
              <span>{useVoiceInput ? "⌨️ Switch to Text Mode" : "🎙️ Switch to Voice Protégé Mode"}</span>
            </button>
          </div>
        </div>
      )}

      {/* Voice Recorder Mode for Protégé */}
      {!isTrap && useVoiceInput ? (
        <VoiceRecorder
          onSubmitVoice={handleVoiceSubmit}
          isSubmitting={isSubmitting}
          prosodySignals={lastFeedback?.evaluation?.prosody_signals ?? null}
          label="Teach Your Peer Out Loud"
          submitButtonText="Submit Spoken Explanation & Analyze Prosody"
        />
      ) : (
        /* Text Response Form (Used for Misconception Trap & Text Protégé fallback) */
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="p-5 rounded-2xl bg-neutral-900/60 border border-neutral-800 flex flex-col gap-2">
            <label className="text-xs font-semibold text-neutral-300 uppercase tracking-wide">
              {isTrap
                ? "Identify the Bug & Explain Why the Premise Fails:"
                : "Explain It to Your Peer in Your Own Words:"}
            </label>
            <textarea
              value={responseInput}
              onChange={(e) => setResponseInput(e.target.value)}
              placeholder={
                isTrap
                  ? "The hidden bug occurs because... In the edge case where..., the logic fails by..."
                  : "The reason this happens is because... Think of it like..."
              }
              rows={4}
              className={`w-full rounded-xl bg-neutral-950 border border-neutral-800 px-4 py-3 text-xs md:text-sm text-neutral-100 placeholder-neutral-500 focus:outline-none focus:ring-2 ${
                isTrap ? "focus:ring-rose-500" : "focus:ring-purple-500"
              }`}
              disabled={isSubmitting}
            />
          </div>

          <div className="flex items-center justify-between gap-4">
            {errorMessage && (
              <span className="text-xs text-rose-400 font-medium">⚠️ {errorMessage}</span>
            )}
            {!errorMessage && (
              <span className="text-xs text-neutral-500">
                {isTrap
                  ? "Scores &ge; 85% grant permanent mastery and advance the concept."
                  : "Teaching peers deepens neurological retention (Protégé Effect)."}
              </span>
            )}

            <button
              type="submit"
              disabled={isSubmitting || !responseInput.trim()}
              className={`px-6 py-2.5 rounded-xl font-bold text-xs md:text-sm text-black shadow-lg transition-all disabled:opacity-50 ${
                isTrap
                  ? "bg-rose-500 hover:bg-rose-400 shadow-rose-500/20"
                  : "bg-purple-400 hover:bg-purple-300 shadow-purple-500/20"
              }`}
            >
              {isSubmitting ? "Evaluating Analysis..." : "Submit Analysis"}
            </button>
          </div>
        </form>
      )}

      {/* Feedback Banner */}
      {lastFeedback && (
        <div className="p-5 rounded-2xl bg-neutral-900 border border-neutral-700 text-white flex flex-col gap-3 shadow-lg">
          <div className="flex items-center justify-between">
            <span
              className={`text-xs font-bold uppercase tracking-wide ${
                lastFeedback.concept_mastered ? "text-emerald-400" : "text-amber-400"
              }`}
            >
              {lastFeedback.concept_mastered
                ? "🎉 Concept Mastered! Advanced to Next Node in DAG"
                : "Challenge Turn Evaluated"}
            </span>
            <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-black/40 text-neutral-300">
              Mastery: {Math.round(lastFeedback.updated_mastery_rating * 100)}%
            </span>
          </div>

          <p className="text-xs md:text-sm text-neutral-200 leading-relaxed font-sans">
            {lastFeedback.evaluation.feedback}
          </p>

          {/* Prosody Telemetry Snapshot in Feedback if Voice was used */}
          {lastFeedback.evaluation.prosody_signals && (
            <div className="p-3 rounded-xl bg-purple-950/30 border border-purple-500/30 flex flex-wrap items-center gap-3 text-xs">
              <span className="font-semibold text-purple-300">🎙️ Spoken Prosody:</span>
              <span className="text-neutral-300 font-mono">
                {Math.round(lastFeedback.evaluation.prosody_signals.speech_rate_wpm)} WPM
              </span>
              <span className="text-neutral-400">•</span>
              <span className="text-purple-300 font-mono">
                {lastFeedback.evaluation.prosody_signals.hesitation_pause_count} pauses (&gt;1.5s)
              </span>
              <span className="text-neutral-400">•</span>
              <span className="text-amber-300 font-mono">
                {(lastFeedback.evaluation.prosody_signals.filler_word_ratio * 100).toFixed(1)}% fillers
              </span>
              <span className="text-neutral-400">•</span>
              <span className="text-emerald-300 font-medium">
                {lastFeedback.evaluation.prosody_signals.fluency_signal}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
