"use client";

import React, { useEffect, useState } from "react";
import Navbar from "@/components/Navbar";
import SessionResumeCard from "@/components/SessionResumeCard";
import { getStudentAnalytics, SessionResumeArtifact, StudentAnalyticsDashboard } from "@/lib/api";
import { BookOpen, Search, Filter, RefreshCw, Sparkles, AlertCircle } from "lucide-react";

export default function ResumesVaultPage() {
  const [analytics, setAnalytics] = useState<StudentAnalyticsDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedDomain, setSelectedDomain] = useState<string>("ALL");
  const [dueOnly, setDueOnly] = useState(false);

  useEffect(() => {
    fetchAnalytics();
  }, []);

  const fetchAnalytics = async () => {
    setLoading(true);
    try {
      const data = await getStudentAnalytics("student_dev_01");
      setAnalytics(data);
    } catch (err) {
      console.error("Failed to load resumes vault:", err);
    } finally {
      setLoading(false);
    }
  };

  const rawResumes: SessionResumeArtifact[] =
    analytics?.lessons_learned_vault?.recent_resumes || [];

  const domains = Array.from(new Set(rawResumes.map((r) => r.domain)));

  const filteredResumes = rawResumes.filter((resume) => {
    if (dueOnly && !resume.due_for_review) return false;
    if (selectedDomain !== "ALL" && resume.domain !== selectedDomain) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchModel = resume.core_mental_model?.toLowerCase().includes(q);
      const matchDomain = resume.domain?.toLowerCase().includes(q);
      const matchTechnique = resume.most_effective_technique?.toLowerCase().includes(q);
      if (!matchModel && !matchDomain && !matchTechnique) return false;
    }
    return true;
  });

  return (
    <div className="min-h-screen flex flex-col bg-transparent text-slate-900 dark:text-zinc-100 transition-colors">
      <Navbar />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-8 space-y-6">
        {/* Header Strip */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-zinc-800">
          <div>
            <div className="flex items-center gap-2">
              <div className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
                <BookOpen className="w-5 h-5" />
              </div>
              <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-zinc-100">
                Session Résumé Vault
              </h1>
            </div>
            <p className="text-xs text-slate-500 dark:text-zinc-400 mt-1">
              Permanent high-signal mental models, winning analogies, and conquered misconceptions generated across completed sessions.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={fetchAnalytics}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-200 dark:border-zinc-800 text-xs font-semibold text-slate-700 dark:text-zinc-300 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
              <span>Refresh Vault</span>
            </button>
          </div>
        </div>

        {/* Filter Controls Bar */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 p-3 rounded-2xl bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 shadow-2xs">
          {/* Search Box */}
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-2.5 w-3.5 h-3.5 text-slate-400" />
            <input
              type="text"
              placeholder="Search mental models, analogies, or techniques..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 rounded-xl text-xs bg-slate-50 dark:bg-zinc-850 border border-slate-200 dark:border-zinc-700/60 text-slate-900 dark:text-zinc-100 placeholder:text-slate-400 focus:outline-hidden focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {/* Domain Dropdown */}
            <select
              value={selectedDomain}
              onChange={(e) => setSelectedDomain(e.target.value)}
              className="px-3 py-1.5 rounded-xl text-xs bg-slate-50 dark:bg-zinc-850 border border-slate-200 dark:border-zinc-700/60 text-slate-700 dark:text-zinc-300 focus:outline-hidden focus:ring-1 focus:ring-indigo-500"
            >
              <option value="ALL">All Domains</option>
              {domains.map((dom) => (
                <option key={dom} value={dom}>
                  {dom.replace("_", " ").toUpperCase()}
                </option>
              ))}
            </select>

            {/* Due for Review Toggle */}
            <button
              onClick={() => setDueOnly(!dueOnly)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all ${
                dueOnly
                  ? "bg-amber-500/10 border-amber-500/40 text-amber-700 dark:text-amber-400 ring-1 ring-amber-500/30"
                  : "bg-slate-50 dark:bg-zinc-850 border-slate-200 dark:border-zinc-700/60 text-slate-600 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-zinc-200"
              }`}
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Due for Review</span>
            </button>
          </div>
        </div>

        {/* Resumes Grid */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-80 rounded-2xl bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 animate-pulse p-6 space-y-4"
              >
                <div className="h-5 bg-slate-200 dark:bg-zinc-800 rounded w-1/3" />
                <div className="h-24 bg-slate-100 dark:bg-zinc-850 rounded-xl" />
                <div className="h-16 bg-slate-100 dark:bg-zinc-850 rounded-xl" />
              </div>
            ))}
          </div>
        ) : filteredResumes.length === 0 ? (
          <div className="p-12 text-center rounded-2xl border border-dashed border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/50 space-y-3">
            <BookOpen className="w-10 h-10 text-slate-400 mx-auto" />
            <h3 className="text-sm font-bold text-slate-800 dark:text-zinc-200">
              No Session Résumés Found
            </h3>
            <p className="text-xs text-slate-500 dark:text-zinc-400 max-w-sm mx-auto">
              Complete a study session or take an Adaptive Mini-Exam to synthesize and save permanent mental model cards into your vault.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {filteredResumes.map((resume) => (
              <SessionResumeCard key={resume.session_id} resume={resume} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
