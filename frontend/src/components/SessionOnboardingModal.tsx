"use client";

import React, { useState } from "react";
import { SessionInitResponse, initSession } from "@/lib/api";

interface SessionOnboardingModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSessionInitialized: (initData: SessionInitResponse) => void;
}

export function SessionOnboardingModal({
  isOpen,
  onClose,
  onSessionInitialized,
}: SessionOnboardingModalProps) {
  const [studentId, setStudentId] = useState<string>("student_dev_01");
  const [domain, setDomain] = useState<string>("computer_science");
  const [topicTitle, setTopicTitle] = useState<string>("Recursion & Call Stacks");
  const [mode, setMode] = useState<"AI_GUIDED" | "SELF_GUIDED">("AI_GUIDED");
  const [resourceScope, setResourceScope] = useState<"STRICT_UPLOAD_ONLY" | "ENRICHED_EXTERNAL">(
    "STRICT_UPLOAD_ONLY"
  );
  const [urlsText, setUrlsText] = useState<string>("");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setSelectedFiles(Array.from(e.target.files));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!topicTitle.trim()) {
      setErrorMessage("Please enter a topic title.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const formData = new FormData();
      formData.append("student_id", studentId);
      formData.append("domain", domain);
      formData.append("topic_title", topicTitle.trim());
      formData.append("mode", mode);
      formData.append("resource_scope", resourceScope);

      if (urlsText.trim()) {
        formData.append("urls", urlsText.trim());
      }

      selectedFiles.forEach((file) => {
        formData.append("files", file);
      });

      const response = await initSession(formData);
      onSessionInitialized(response);
      onClose();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage("Failed to initialize session.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl w-full max-w-2xl shadow-2xl overflow-hidden my-8">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between bg-gray-50/50 dark:bg-gray-950/40">
          <div>
            <h3 className="text-lg font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
              <span>🚀</span>
              <span>Start Adaptive Learning Session (Slice 2)</span>
            </h3>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              Multimodal Ingestion • Concept DAG Extraction • Baseline Diagnostic
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
          >
            ✕
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5 text-xs">
          {errorMessage && (
            <div className="p-3 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300">
              {errorMessage}
            </div>
          )}

          {/* Academic Domain & Topic */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block font-semibold text-gray-700 dark:text-gray-300 mb-1">
                Academic Domain
              </label>
              <select
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 font-medium"
              >
                <option value="computer_science">Computer Science</option>
                <option value="biology">Cellular &amp; Molecular Biology</option>
                <option value="mathematics">Discrete Mathematics</option>
                <option value="physics">Classical &amp; Quantum Physics</option>
                <option value="literature">World Literature &amp; Rhetoric</option>
              </select>
            </div>

            <div>
              <label className="block font-semibold text-gray-700 dark:text-gray-300 mb-1">
                Primary Topic Title *
              </label>
              <input
                type="text"
                value={topicTitle}
                onChange={(e) => setTopicTitle(e.target.value)}
                placeholder="e.g., Recursion & Call Stacks"
                className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 font-medium"
                required
              />
            </div>
          </div>

          {/* Mode & Resource Scope */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block font-semibold text-gray-700 dark:text-gray-300 mb-1">
                Learning Mode
              </label>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setMode("AI_GUIDED")}
                  className={`flex-1 py-1.5 rounded-lg border text-xs font-semibold transition ${
                    mode === "AI_GUIDED"
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-gray-50 dark:bg-gray-800 border-gray-300 dark:border-gray-700 text-gray-700 dark:text-gray-300"
                  }`}
                >
                  AI-Guided
                </button>
                <button
                  type="button"
                  onClick={() => setMode("SELF_GUIDED")}
                  className={`flex-1 py-1.5 rounded-lg border text-xs font-semibold transition ${
                    mode === "SELF_GUIDED"
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-gray-50 dark:bg-gray-800 border-gray-300 dark:border-gray-700 text-gray-700 dark:text-gray-300"
                  }`}
                >
                  Self-Guided
                </button>
              </div>
            </div>

            <div>
              <label className="block font-semibold text-gray-700 dark:text-gray-300 mb-1">
                Resource Scope
              </label>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setResourceScope("STRICT_UPLOAD_ONLY")}
                  className={`flex-1 py-1.5 rounded-lg border text-xs font-semibold transition ${
                    resourceScope === "STRICT_UPLOAD_ONLY"
                      ? "bg-sky-600 text-white border-sky-600"
                      : "bg-gray-50 dark:bg-gray-800 border-gray-300 dark:border-gray-700 text-gray-700 dark:text-gray-300"
                  }`}
                >
                  Strict: Only Files
                </button>
                <button
                  type="button"
                  onClick={() => setResourceScope("ENRICHED_EXTERNAL")}
                  className={`flex-1 py-1.5 rounded-lg border text-xs font-semibold transition ${
                    resourceScope === "ENRICHED_EXTERNAL"
                      ? "bg-sky-600 text-white border-sky-600"
                      : "bg-gray-50 dark:bg-gray-800 border-gray-300 dark:border-gray-700 text-gray-700 dark:text-gray-300"
                  }`}
                >
                  Enriched External
                </button>
              </div>
            </div>
          </div>

          {/* Multimodal Resource Uploads */}
          <div className="space-y-3 pt-2 border-t border-gray-200 dark:border-gray-800">
            <div>
              <label className="block font-semibold text-gray-700 dark:text-gray-300 mb-1">
                Attach Study Documents (PDFs, Notes)
              </label>
              <input
                type="file"
                multiple
                accept=".pdf,.txt,.md,.py"
                onChange={handleFileChange}
                className="w-full text-xs text-gray-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 dark:file:bg-blue-950 dark:file:text-blue-300"
              />
              {selectedFiles.length > 0 && (
                <p className="mt-1 text-[11px] text-emerald-600 dark:text-emerald-400">
                  ✓ {selectedFiles.length} file(s) selected: {selectedFiles.map((f) => f.name).join(", ")}
                </p>
              )}
            </div>

            <div>
              <label className="block font-semibold text-gray-700 dark:text-gray-300 mb-1">
                YouTube or Web Article URLs (one per line)
              </label>
              <textarea
                rows={2}
                value={urlsText}
                onChange={(e) => setUrlsText(e.target.value)}
                placeholder="https://www.youtube.com/watch?v=...&#10;https://en.wikipedia.org/wiki/..."
                className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 font-mono text-[11px]"
              />
              <p className="text-[10px] text-gray-500 dark:text-gray-400 mt-0.5">
                Exact timestamps and page numbers are preserved across chunks for Level 2 hint citations.
              </p>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-200 dark:border-gray-800">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-700 text-gray-700 dark:text-gray-300 font-semibold hover:bg-gray-100 dark:hover:bg-gray-800"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-5 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-bold flex items-center gap-2 shadow-sm disabled:opacity-50"
            >
              {isSubmitting ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                  <span>Ingesting &amp; Building DAG...</span>
                </>
              ) : (
                <span>Initialize &amp; Generate Diagnostic →</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
