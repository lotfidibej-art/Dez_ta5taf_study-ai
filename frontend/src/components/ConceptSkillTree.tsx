"use client";

import React, { useState } from "react";
import { CheckCircle2, Lock, PlayCircle, BookOpen, ChevronRight, FileText, ExternalLink, Compass, Zap, Award, GraduationCap } from "lucide-react";
import { ConceptNodeState, ResourceChunk } from "@/lib/api";

interface ConceptSkillTreeProps {
  concepts: ConceptNodeState[];
  activeConceptId: string;
  onSelectConcept?: (conceptId: string) => void;
  onSelectLessonStage?: (
    conceptId: string,
    stage: "FOUNDATION" | "PRACTICE" | "CHALLENGE" | "PROTEGE" | "EXAM"
  ) => void;
  mode?: "AI_GUIDED" | "SELF_GUIDED";
  chunks?: ResourceChunk[];
}

export default function ConceptSkillTree({
  concepts,
  activeConceptId,
  onSelectConcept,
  onSelectLessonStage,
  mode = "AI_GUIDED",
  chunks = [],
}: ConceptSkillTreeProps) {
  const [activeTab, setActiveTab] = useState<"tree" | "citations">("tree");

  const getTierColor = (rating: number) => {
    if (rating < 0.4) return "text-sky-500 border-sky-500/30 bg-sky-500/10";
    if (rating < 0.75) return "text-violet-500 border-violet-500/30 bg-violet-500/10";
    return "text-emerald-500 border-emerald-500/30 bg-emerald-500/10";
  };

  const getTierRing = (rating: number) => {
    if (rating < 0.4) return "stroke-sky-500";
    if (rating < 0.75) return "stroke-violet-500";
    return "stroke-emerald-500";
  };

  return (
    <div className="flex flex-col h-full bg-white/85 dark:bg-zinc-900/85 backdrop-blur-md border-r border-slate-200 dark:border-zinc-800 transition-colors">
      {/* Rail Tabs */}
      <div className="flex border-b border-slate-200 dark:border-zinc-800 px-3 pt-3">
        <button
          onClick={() => setActiveTab("tree")}
          className={`flex-1 pb-2.5 text-xs font-semibold border-b-2 transition-all flex items-center justify-center gap-1.5 ${
            activeTab === "tree"
              ? "border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400"
              : "border-transparent text-slate-500 hover:text-slate-800 dark:text-zinc-400 dark:hover:text-zinc-200"
          }`}
        >
          <PlayCircle className="w-3.5 h-3.5" />
          <span>Skill Tree</span>
          <span className="ml-1 text-[10px] font-mono px-1.5 py-0.2 rounded-full bg-slate-100 dark:bg-zinc-800">
            {concepts.length}
          </span>
        </button>
        <button
          onClick={() => setActiveTab("citations")}
          className={`flex-1 pb-2.5 text-xs font-semibold border-b-2 transition-all flex items-center justify-center gap-1.5 ${
            activeTab === "citations"
              ? "border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400"
              : "border-transparent text-slate-500 hover:text-slate-800 dark:text-zinc-400 dark:hover:text-zinc-200"
          }`}
        >
          <BookOpen className="w-3.5 h-3.5" />
          <span>Citations</span>
          {chunks.length > 0 && (
            <span className="ml-1 text-[10px] font-mono px-1.5 py-0.2 rounded-full bg-slate-100 dark:bg-zinc-800">
              {chunks.length}
            </span>
          )}
        </button>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {activeTab === "tree" ? (
          <div className="relative space-y-4">
            {mode === "SELF_GUIDED" && (
              <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-[11px] text-amber-700 dark:text-amber-300 space-y-1">
                <div className="flex items-center gap-1.5 font-bold">
                  <Compass className="w-3.5 h-3.5 text-amber-500" />
                  <span>Self-Guided Mode Active</span>
                </div>
                <p className="text-[10px] text-amber-600/90 dark:text-amber-400/90 leading-tight">
                  Prerequisites unlocked. Click any concept below to switch topics, or choose your lesson type.
                </p>
              </div>
            )}

            {concepts.map((concept, index) => {
              const isActive = concept.concept_id === activeConceptId;
              const isMastered = concept.status === "MASTERED" || concept.mastery_rating >= 0.85;
              const isLocked = mode === "SELF_GUIDED" ? false : concept.status === "LOCKED";
              const pct = Math.round(concept.mastery_rating * 100);

              return (
                <div key={concept.concept_id} className="relative flex items-start gap-3 group">
                  {/* Vertical connector line */}
                  {index < concepts.length - 1 && (
                    <div
                      className={`absolute left-[15px] top-[32px] w-[2px] h-[calc(100%+8px)] transition-colors ${
                        isMastered
                          ? "bg-emerald-500/50"
                          : isActive
                          ? "bg-indigo-500/40"
                          : "bg-slate-200 dark:bg-zinc-800"
                      }`}
                    />
                  )}

                  {/* Circular Mastery Ring */}
                  <div className="relative z-10 flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-white dark:bg-zinc-900">
                    <svg className="w-8 h-8 -rotate-90" viewBox="0 0 36 36">
                      <circle
                        cx="18"
                        cy="18"
                        r="15"
                        fill="none"
                        className="stroke-slate-200 dark:stroke-zinc-800"
                        strokeWidth="2.5"
                      />
                      <circle
                        cx="18"
                        cy="18"
                        r="15"
                        fill="none"
                        className={`${getTierRing(concept.mastery_rating)} transition-all duration-500`}
                        strokeWidth="2.5"
                        strokeDasharray={94.2}
                        strokeDashoffset={94.2 - (94.2 * (isLocked ? 0 : pct)) / 100}
                        strokeLinecap="round"
                      />
                    </svg>
                    <div className="absolute inset-0 flex items-center justify-center">
                      {isMastered ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                      ) : isLocked ? (
                        <Lock className="w-3.5 h-3.5 text-slate-400 dark:text-zinc-500" />
                      ) : (
                        <span className="text-[10px] font-mono font-bold text-slate-800 dark:text-zinc-200">
                          {pct}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Concept Card Tile */}
                  <div
                    onClick={() => !isLocked && onSelectConcept && onSelectConcept(concept.concept_id)}
                    className={`flex-1 text-left p-2.5 rounded-xl border transition-all ${
                      isLocked ? "cursor-not-allowed opacity-60 border-slate-200/60 dark:border-zinc-800/60" : "cursor-pointer"
                    } ${
                      isActive
                        ? "border-indigo-500/70 bg-indigo-50/50 dark:bg-indigo-950/20 shadow-xs ring-1 ring-indigo-500/30"
                        : !isLocked
                        ? "border-slate-200 dark:border-zinc-800 hover:border-slate-300 dark:hover:border-zinc-700 bg-slate-50/50 dark:bg-zinc-800/20"
                        : ""
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <h4 className="text-xs font-semibold text-slate-900 dark:text-zinc-100 truncate">
                        {concept.title}
                      </h4>
                      <span
                        className={`text-[9px] font-mono px-1.5 py-0.5 rounded-full border font-semibold ${getTierColor(
                          concept.mastery_rating
                        )}`}
                      >
                        {pct}%
                      </span>
                    </div>

                    {concept.prerequisites && concept.prerequisites.length > 0 && (
                      <p className="mt-1 text-[10px] text-slate-500 dark:text-zinc-400 truncate">
                        {mode === "SELF_GUIDED" ? "Prerequisites:" : "Requires:"} {concept.prerequisites.join(", ")}
                      </p>
                    )}

                    {/* Self-guided lesson picker */}
                    {mode === "SELF_GUIDED" && isActive && onSelectLessonStage && (
                      <div
                        className="mt-2.5 pt-2 border-t border-slate-200/60 dark:border-zinc-800/60 flex flex-wrap gap-1.5"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <button
                          type="button"
                          onClick={() => onSelectLessonStage(concept.concept_id, "FOUNDATION")}
                          className="px-2 py-0.5 rounded-lg text-[10px] font-semibold bg-sky-500/10 text-sky-700 dark:text-sky-300 border border-sky-500/20 hover:bg-sky-500/20 transition-all flex items-center gap-1"
                          title="Explain concept with core mental model & interactive quiz"
                        >
                          <BookOpen className="w-2.5 h-2.5" />
                          <span>Explain</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => onSelectLessonStage(concept.concept_id, "PRACTICE")}
                          className="px-2 py-0.5 rounded-lg text-[10px] font-semibold bg-violet-500/10 text-violet-700 dark:text-violet-300 border border-violet-500/20 hover:bg-violet-500/20 transition-all flex items-center gap-1"
                          title="Guided faded example workspace"
                        >
                          <PlayCircle className="w-2.5 h-2.5" />
                          <span>Practice</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => onSelectLessonStage(concept.concept_id, "CHALLENGE")}
                          className="px-2 py-0.5 rounded-lg text-[10px] font-semibold bg-amber-500/10 text-amber-700 dark:text-amber-300 border border-amber-500/20 hover:bg-amber-500/20 transition-all flex items-center gap-1"
                          title="Tackle edge-case misconception trap"
                        >
                          <Zap className="w-2.5 h-2.5" />
                          <span>Trap</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => onSelectLessonStage(concept.concept_id, "PROTEGE")}
                          className="px-2 py-0.5 rounded-lg text-[10px] font-semibold bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20 hover:bg-emerald-500/20 transition-all flex items-center gap-1"
                          title="Teach AI student in protege stage"
                        >
                          <GraduationCap className="w-2.5 h-2.5" />
                          <span>Teach AI</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => onSelectLessonStage(concept.concept_id, "EXAM")}
                          className="px-2 py-0.5 rounded-lg text-[10px] font-semibold bg-rose-500/10 text-rose-700 dark:text-rose-300 border border-rose-500/20 hover:bg-rose-500/20 transition-all flex items-center gap-1"
                          title="Take an on-demand mini-exam for this concept"
                        >
                          <Award className="w-2.5 h-2.5" />
                          <span>Exam</span>
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="space-y-3">
            {chunks.length === 0 ? (
              <div className="p-4 text-center rounded-xl border border-dashed border-slate-200 dark:border-zinc-800 text-xs text-slate-500 dark:text-zinc-400">
                <FileText className="w-6 h-6 mx-auto mb-2 text-slate-400" />
                <p>No primary resource chunks loaded.</p>
                <p className="text-[10px] mt-1 text-slate-400">Upload PDFs or add URLs to unlock cited study materials.</p>
              </div>
            ) : (
              chunks.map((chunk, idx) => (
                <div
                  key={chunk.chunk_id || idx}
                  className="p-3 rounded-xl border border-slate-200 dark:border-zinc-800 bg-slate-50/70 dark:bg-zinc-850/50 text-xs hover:border-indigo-500/40 transition-all"
                >
                  <div className="flex items-center justify-between gap-1 text-[11px] font-semibold text-indigo-600 dark:text-indigo-400 mb-1">
                    <span className="truncate flex items-center gap-1">
                      <FileText className="w-3 h-3 flex-shrink-0" />
                      {chunk.source_name}
                    </span>
                    <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-indigo-50 dark:bg-indigo-950/50 text-indigo-700 dark:text-indigo-300 border border-indigo-200/50 dark:border-indigo-800/40">
                      {chunk.source_location}
                    </span>
                  </div>
                  <p className="text-slate-600 dark:text-zinc-300 text-[11px] line-clamp-3 leading-relaxed">
                    {chunk.content}
                  </p>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}
