"use client";

import React, { useState } from "react";
import {
  DiagnosticAnswer,
  DiagnosticEvaluationResponse,
  DiagnosticQuestion,
  submitDiagnosticAnswers,
} from "@/lib/api";

interface BaselineDiagnosticCardProps {
  sessionId: string;
  topicTitle: string;
  questions: DiagnosticQuestion[];
  onDiagnosticCompleted: (evalResult: DiagnosticEvaluationResponse) => void;
}

export function BaselineDiagnosticCard({
  sessionId,
  topicTitle,
  questions,
  onDiagnosticCompleted,
}: BaselineDiagnosticCardProps) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleAnswerChange = (questionId: string, text: string) => {
    setAnswers((prev) => ({ ...prev, [questionId]: text }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const formattedAnswers: DiagnosticAnswer[] = questions.map((q) => ({
      question_id: q.question_id,
      concept_id: q.concept_id,
      answer_text: answers[q.question_id]?.trim() || "I am unsure about this concept.",
    }));

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const response = await submitDiagnosticAnswers(sessionId, formattedAnswers);
      onDiagnosticCompleted(response);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage("Failed to evaluate diagnostic answers.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const getTierColor = (tier: string) => {
    switch (tier) {
      case "FOUNDATIONAL":
        return "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300 border-sky-300 dark:border-sky-800";
      case "INTERMEDIATE":
        return "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 border-amber-300 dark:border-amber-800";
      case "ADVANCED":
        return "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300 border-purple-300 dark:border-purple-800";
      default:
        return "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300";
    }
  };

  return (
    <div className="border border-indigo-200 bg-indigo-50/40 dark:bg-indigo-950/20 dark:border-indigo-800 rounded-2xl p-6 shadow-sm space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-indigo-200 dark:border-indigo-800 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xl">📋</span>
            <span className="text-xs font-bold uppercase tracking-wider text-indigo-600 dark:text-indigo-400">
              Agent 3 • Baseline Diagnostic
            </span>
          </div>
          <h3 className="text-lg font-bold text-gray-900 dark:text-gray-100 mt-1">
            Initial 3-Question Diagnostic: {topicTitle}
          </h3>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
            Answer concisely to calibrate your live comprehension rating and unlock the appropriate tier.
          </p>
        </div>
        <span className="self-start sm:self-auto px-3 py-1 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200">
          3 Calibrated Questions
        </span>
      </div>

      {errorMessage && (
        <div className="p-3 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-xs text-red-700 dark:text-red-300">
          {errorMessage}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        {questions.map((q, idx) => (
          <div
            key={q.question_id}
            className="p-4 rounded-xl bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 space-y-3 shadow-sm"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-indigo-600 text-white flex items-center justify-center text-xs font-bold">
                  {idx + 1}
                </span>
                <span className="text-xs font-semibold text-gray-900 dark:text-gray-100">
                  Concept: {q.concept_title}
                </span>
              </div>
              <span
                className={`text-[10px] font-mono px-2 py-0.5 rounded border font-semibold ${getTierColor(
                  q.depth_tier
                )}`}
              >
                {q.depth_tier}
              </span>
            </div>

            <p className="text-xs font-medium text-gray-800 dark:text-gray-200">
              {q.question_text}
            </p>

            <textarea
              rows={3}
              value={answers[q.question_id] || ""}
              onChange={(e) => handleAnswerChange(q.question_id, e.target.value)}
              placeholder="Explain the mechanism, reason, or trade-off in your own words..."
              className="w-full px-3 py-2 text-xs rounded-lg border border-gray-300 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        ))}

        <div className="flex items-center justify-between pt-2">
          <span className="text-[11px] text-gray-500 italic">
            Tip: Be honest and explain the &ldquo;why&rdquo;. Don&apos;t worry about mistakes—the AI adapts to your current level.
          </span>
          <button
            type="submit"
            disabled={isSubmitting}
            className="px-6 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs flex items-center gap-2 shadow-md transition disabled:opacity-50"
          >
            {isSubmitting ? (
              <>
                <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                <span>Evaluating via Gemini 3.8 Flash...</span>
              </>
            ) : (
              <span>Submit Diagnostic &amp; Enter Workspace →</span>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
