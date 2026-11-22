"use client";

import React, { useEffect, useState } from "react";
import {
  ResourceChunk,
  SelfGuidedInjectResponse,
  SessionState,
  getSessionChunks,
  injectSelfGuidedSnippet,
} from "@/lib/api";

interface SelfGuidedReaderProps {
  session: SessionState;
  onSnippetInjected?: (response: SelfGuidedInjectResponse) => void;
  onClose?: () => void;
}

export const SelfGuidedReader: React.FC<SelfGuidedReaderProps> = ({
  session,
  onSnippetInjected,
  onClose,
}) => {
  const [chunks, setChunks] = useState<ResourceChunk[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [selectedSnippet, setSelectedSnippet] = useState<string>("");
  const [isInjecting, setIsInjecting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    async function loadChunks() {
      setIsLoading(true);
      try {
        const data = await getSessionChunks(session.session_id);
        if (isMounted) setChunks(data);
      } catch (err: unknown) {
        if (isMounted) {
          const msg = err instanceof Error ? err.message : String(err);
          setErrorMessage(msg);
        }
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }
    loadChunks();
    return () => {
      isMounted = false;
    };
  }, [session.session_id]);

  const handleTextSelection = () => {
    const sel = window.getSelection();
    if (sel && sel.toString().trim().length > 10) {
      setSelectedSnippet(sel.toString().trim());
    }
  };

  const handleInject = async (text: string, intent: "EXPLAIN" | "QUIZ") => {
    if (!text.trim()) return;
    setIsInjecting(true);
    setErrorMessage(null);

    try {
      const resp = await injectSelfGuidedSnippet(session.session_id, {
        selected_text: text,
        intent,
      });
      if (onSnippetInjected) {
        onSnippetInjected(resp);
      }
      setSelectedSnippet("");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMessage(msg);
    } finally {
      setIsInjecting(false);
    }
  };

  return (
    <div className="flex flex-col gap-5 w-full max-w-5xl mx-auto p-6 rounded-2xl bg-neutral-900/90 border border-neutral-800 shadow-2xl backdrop-blur-md">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-neutral-800 pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
              Self-Guided Document Reader
            </span>
            <span className="text-neutral-500 text-xs">
              {chunks.length} Ingested Passages Available
            </span>
          </div>
          <h2 className="text-xl font-bold text-white tracking-tight">
            Explore &amp; Inject Learning Targets
          </h2>
        </div>

        {onClose && (
          <button
            onClick={onClose}
            className="px-3 py-1.5 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-neutral-300 text-xs font-semibold"
          >
            Close Reader ✕
          </button>
        )}
      </div>

      {/* Floating Selection Tooltip Banner */}
      {selectedSnippet && (
        <div className="p-4 rounded-xl bg-cyan-950/40 border border-cyan-500/30 flex flex-col md:flex-row items-start md:items-center justify-between gap-3 shadow-lg animate-fadeIn">
          <div className="flex-1 text-xs text-neutral-200">
            <span className="font-bold text-cyan-300 block mb-0.5">Selected Passage:</span>
            <p className="line-clamp-2 italic font-serif">&ldquo;{selectedSnippet}&rdquo;</p>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => handleInject(selectedSnippet, "EXPLAIN")}
              disabled={isInjecting}
              className="px-3.5 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-black text-xs font-bold transition disabled:opacity-50"
            >
              Explain This (Foundation)
            </button>
            <button
              onClick={() => handleInject(selectedSnippet, "QUIZ")}
              disabled={isInjecting}
              className="px-3.5 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-black text-xs font-bold transition disabled:opacity-50"
            >
              Quiz Me (Scaffolding)
            </button>
            <button
              onClick={() => setSelectedSnippet("")}
              className="text-neutral-400 hover:text-white text-xs px-2"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Error message */}
      {errorMessage && (
        <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs font-medium">
          ⚠️ {errorMessage}
        </div>
      )}

      {/* Content Stream */}
      {isLoading ? (
        <div className="text-center py-16 text-neutral-500 text-sm">
          Loading document excerpts from PostgreSQL...
        </div>
      ) : chunks.length === 0 ? (
        <div className="text-center py-16 text-neutral-500 text-sm">
          No external PDF or web resources were uploaded for this session. Use canonical study mode or start an enriched session.
        </div>
      ) : (
        <div onMouseUp={handleTextSelection} className="space-y-4 max-h-[600px] overflow-y-auto pr-2">
          {chunks.map((chunk, idx) => (
            <div
              key={chunk.chunk_id || idx}
              className="p-5 rounded-2xl bg-neutral-950/60 border border-neutral-800/80 hover:border-neutral-700 transition flex flex-col gap-3 group"
            >
              <div className="flex items-center justify-between text-xs text-neutral-400 border-b border-neutral-800/50 pb-2">
                <span className="font-semibold text-neutral-200 flex items-center gap-1.5">
                  <span>📄</span> {chunk.source_name}
                </span>
                <span className="px-2 py-0.5 rounded bg-neutral-800 text-neutral-300 font-mono text-[11px]">
                  {chunk.source_location}
                </span>
              </div>

              <p className="text-xs md:text-sm text-neutral-300 leading-relaxed whitespace-pre-wrap select-text font-serif">
                {chunk.content}
              </p>

              <div className="flex items-center justify-end gap-2 opacity-80 group-hover:opacity-100 transition">
                <button
                  onClick={() => handleInject(chunk.content, "EXPLAIN")}
                  disabled={isInjecting}
                  className="px-3 py-1 rounded-lg bg-neutral-800 hover:bg-emerald-500/20 hover:text-emerald-300 text-neutral-400 text-xs font-medium transition"
                >
                  Explain Passage
                </button>
                <button
                  onClick={() => handleInject(chunk.content, "QUIZ")}
                  disabled={isInjecting}
                  className="px-3 py-1 rounded-lg bg-neutral-800 hover:bg-amber-500/20 hover:text-amber-300 text-neutral-400 text-xs font-medium transition"
                >
                  Quiz On This
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
