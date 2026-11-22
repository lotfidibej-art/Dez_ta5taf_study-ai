"use client";

import React, { useState } from "react";
import { X, CheckCircle2, AlertTriangle, ArrowRight, ArrowLeft, Send, Sparkles, BookOpen, Clock, Calendar } from "lucide-react";
import { MiniExamPayload, ExamResult, ExamSubmitRequest, submitMiniExam } from "@/lib/api";

interface MiniExamModalProps {
  exam: MiniExamPayload;
  sessionId: string;
  onClose: () => void;
  onExamCompleted: (result: ExamResult) => void;
}

export default function MiniExamModal({
  exam,
  sessionId,
  onClose,
  onExamCompleted,
}: MiniExamModalProps) {
  const [currentIdx, setCurrentIdx] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [examResult, setExamResult] = useState<ExamResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const questions = exam.questions || [];
  const currentQ = questions[currentIdx];

  const handleSelectOption = (qId: string, option: string) => {
    setAnswers((prev) => ({ ...prev, [qId]: option }));
  };

  const handleTextAnswer = (qId: string, text: string) => {
    setAnswers((prev) => ({ ...prev, [qId]: text }));
  };

  const isCurrentAnswered = () => {
    if (!currentQ) return false;
    const ans = answers[currentQ.question_id];
    return typeof ans === "string" && ans.trim().length > 0;
  };

  const handleSubmitExam = async () => {
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      const submissions = questions.map((q) => ({
        question_id: q.question_id,
        answer: answers[q.question_id] || "",
      }));

      const payload: ExamSubmitRequest = { submissions };
      const res = await submitMiniExam(sessionId, payload);
      setExamResult(res);
      onExamCompleted(res);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to grade mini-exam.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-2xl rounded-2xl bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-zinc-800 bg-slate-50/70 dark:bg-zinc-850/40">
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-zinc-100">
                {examResult ? "Adaptive Mini-Exam Results" : "Adaptive Mini-Exam Check"}
              </h3>
              <p className="text-[11px] text-slate-500 dark:text-zinc-400">
                {examResult
                  ? "Psychometric evaluation complete"
                  : "Targeting your session's diagnosed misconceptions • Hints disabled"}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-zinc-200 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6">
          {errorMsg && (
            <div className="mb-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-600 dark:text-rose-400 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          {!examResult ? (
            <div className="space-y-6">
              {/* Progress Bar & Question Step Counter */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs text-slate-500 dark:text-zinc-400">
                  <span className="font-semibold text-slate-800 dark:text-zinc-200">
                    Question {currentIdx + 1} of {questions.length}
                  </span>
                  <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-slate-100 dark:bg-zinc-800">
                    {currentQ?.type}
                  </span>
                </div>
                <div className="flex gap-1.5">
                  {questions.map((q, idx) => {
                    const isAnswered = answers[q.question_id]?.trim().length > 0;
                    const isCurrent = idx === currentIdx;
                    return (
                      <div
                        key={q.question_id}
                        className={`h-1.5 flex-1 rounded-full transition-all ${
                          isCurrent
                            ? "bg-indigo-600 dark:bg-indigo-400"
                            : isAnswered
                            ? "bg-emerald-500"
                            : "bg-slate-200 dark:bg-zinc-800"
                        }`}
                      />
                    );
                  })}
                </div>
              </div>

              {/* Active Question Content */}
              {currentQ && (
                <div className="space-y-4">
                  <div className="text-sm font-medium text-slate-900 dark:text-zinc-100 leading-relaxed">
                    {currentQ.prompt}
                  </div>

                  {/* Faded Context if applicable */}
                  {currentQ.faded_context && (
                    <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-zinc-850/80 border border-slate-200 dark:border-zinc-800 text-xs font-mono text-slate-800 dark:text-zinc-200 whitespace-pre-wrap leading-relaxed">
                      {currentQ.faded_context}
                    </div>
                  )}

                  {/* Question Options for MCQ */}
                  {currentQ.type === "MCQ" && currentQ.options && (
                    <div className="space-y-2">
                      {currentQ.options.map((option, optIdx) => {
                        const isSelected = answers[currentQ.question_id] === option;
                        return (
                          <button
                            key={optIdx}
                            onClick={() => handleSelectOption(currentQ.question_id, option)}
                            className={`w-full text-left p-3.5 rounded-xl border text-xs leading-relaxed transition-all flex items-start gap-3 ${
                              isSelected
                                ? "border-indigo-600 bg-indigo-50/60 dark:bg-indigo-950/30 text-indigo-900 dark:text-indigo-200 ring-1 ring-indigo-500/30"
                                : "border-slate-200 dark:border-zinc-800 hover:border-slate-300 dark:hover:border-zinc-700 bg-white dark:bg-zinc-850/40 text-slate-700 dark:text-zinc-300"
                            }`}
                          >
                            <span
                              className={`flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full border mt-0.5 text-[10px] font-mono ${
                                isSelected
                                  ? "border-indigo-600 bg-indigo-600 text-white"
                                  : "border-slate-300 dark:border-zinc-600 text-slate-500"
                              }`}
                            >
                              {String.fromCharCode(65 + optIdx)}
                            </span>
                            <span className="flex-1">{option}</span>
                          </button>
                        );
                      })}
                    </div>
                  )}

                  {/* Open-ended text input for Faded Transfer / Causal Synthesis */}
                  {currentQ.type !== "MCQ" && (
                    <div>
                      <textarea
                        value={answers[currentQ.question_id] || ""}
                        onChange={(e) => handleTextAnswer(currentQ.question_id, e.target.value)}
                        placeholder="Explain the causal mechanism or fill in the missing reasoning step..."
                        rows={5}
                        className="w-full resize-none rounded-xl border border-slate-200 dark:border-zinc-800 bg-slate-50/70 dark:bg-zinc-850/60 p-3.5 text-xs text-slate-800 dark:text-zinc-200 placeholder:text-slate-400 focus:outline-hidden focus:ring-1 focus:ring-indigo-500 leading-relaxed font-mono"
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            /* Results View */
            <div className="space-y-6">
              {/* Score Banner */}
              <div
                className={`p-5 rounded-2xl border text-center space-y-2 ${
                  examResult.passed
                    ? "bg-emerald-50/80 dark:bg-emerald-950/20 border-emerald-500/30"
                    : "bg-amber-50/80 dark:bg-amber-950/20 border-amber-500/30"
                }`}
              >
                <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider font-mono">
                  {examResult.passed ? (
                    <span className="text-emerald-700 dark:text-emerald-400">Mastery Verified</span>
                  ) : (
                    <span className="text-amber-700 dark:text-amber-400">Reinforcement Recommended</span>
                  )}
                </div>
                <div className="text-4xl font-extrabold font-mono text-slate-900 dark:text-zinc-100">
                  {Math.round(examResult.exam_score * 100)}%
                </div>
                <p className="text-xs text-slate-600 dark:text-zinc-400 max-w-md mx-auto">
                  {examResult.passed
                    ? "Exceptional causal comprehension. The mental invariants have been thoroughly verified against past misconceptions."
                    : "Good attempt! Review the specific counter-examples below before your next spaced repetition window."}
                </p>
              </div>

              {/* Spaced Repetition Next Target */}
              {examResult.resume && (
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="p-3.5 rounded-xl border border-slate-200 dark:border-zinc-800 bg-slate-50/60 dark:bg-zinc-850/40">
                    <span className="flex items-center gap-1.5 text-slate-500 dark:text-zinc-400 text-[11px] mb-1">
                      <Calendar className="w-3.5 h-3.5 text-indigo-500" />
                      Next Review Target
                    </span>
                    <span className="font-mono font-bold text-slate-900 dark:text-zinc-100">
                      {examResult.resume.recommended_refresher_date}
                    </span>
                  </div>
                  <div className="p-3.5 rounded-xl border border-slate-200 dark:border-zinc-800 bg-slate-50/60 dark:bg-zinc-850/40">
                    <span className="flex items-center gap-1.5 text-slate-500 dark:text-zinc-400 text-[11px] mb-1">
                      <Clock className="w-3.5 h-3.5 text-purple-500" />
                      Mastery Velocity
                    </span>
                    <span className="font-mono font-bold text-slate-900 dark:text-zinc-100">
                      +{(examResult.resume.mastery_velocity * 10).toFixed(2)} / 10m
                    </span>
                  </div>
                </div>
              )}

              {/* Graded Questions Breakdown */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold text-slate-800 dark:text-zinc-200">
                  Item Analysis
                </h4>
                <div className="space-y-2">
                  {examResult.graded_questions.map((item, idx) => {
                    const isGood = item.score >= 0.75;
                    return (
                      <div
                        key={item.question_id || idx}
                        className={`p-3 rounded-xl border text-xs space-y-1 ${
                          isGood
                            ? "border-emerald-500/20 bg-emerald-50/30 dark:bg-emerald-950/10"
                            : "border-amber-500/20 bg-amber-50/30 dark:bg-amber-950/10"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-slate-800 dark:text-zinc-200">
                            Question {idx + 1}
                          </span>
                          <span
                            className={`font-mono text-[11px] font-bold ${
                              isGood ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400"
                            }`}
                          >
                            {Math.round(item.score * 100)}%
                          </span>
                        </div>
                        <p className="text-slate-600 dark:text-zinc-400 text-[11px]">
                          {item.feedback}
                        </p>
                        {item.lingering_flaw && (
                          <div className="text-[10px] text-rose-600 dark:text-rose-400 font-medium pt-1">
                            Lingering Trap: {item.lingering_flaw}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer Navigation */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-slate-200 dark:border-zinc-800 bg-slate-50/70 dark:bg-zinc-850/40">
          {!examResult ? (
            <>
              <button
                onClick={() => setCurrentIdx((prev) => Math.max(0, prev - 1))}
                disabled={currentIdx === 0}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold text-slate-600 dark:text-zinc-400 hover:bg-slate-200 dark:hover:bg-zinc-800 disabled:opacity-40 transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Previous</span>
              </button>

              {currentIdx < questions.length - 1 ? (
                <button
                  onClick={() => setCurrentIdx((prev) => Math.min(questions.length - 1, prev + 1))}
                  disabled={!isCurrentAnswered()}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 transition-all shadow-xs"
                >
                  <span>Next</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              ) : (
                <button
                  onClick={handleSubmitExam}
                  disabled={isSubmitting || !isCurrentAnswered()}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50 transition-all shadow-xs"
                >
                  <Send className="w-3.5 h-3.5" />
                  <span>{isSubmitting ? "Grading..." : "Submit Mini-Exam"}</span>
                </button>
              )}
            </>
          ) : (
            <div className="w-full flex justify-end gap-2">
              <button
                onClick={onClose}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 transition-all shadow-xs"
              >
                Return to Studio
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
