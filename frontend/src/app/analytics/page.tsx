"use client";

import React, { useEffect, useState } from "react";
import Navbar from "@/components/Navbar";
import {
  getStudentAnalytics,
  StudentAnalyticsDashboard,
  FieldMastery,
  TechniqueStat,
} from "@/lib/api";
import {
  Activity,
  Award,
  BookOpen,
  Calendar,
  CheckCircle2,
  Clock,
  Compass,
  Gauge,
  HelpCircle,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Zap,
} from "lucide-react";
import {
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ComposedChart,
  Area,
  Line,
  Legend,
} from "recharts";

export default function AnalyticsPage() {
  const [data, setData] = useState<StudentAnalyticsDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedDomain, setSelectedDomain] = useState<string>("computer_science");
  const [misconceptionFilter, setMisconceptionFilter] = useState("");

  useEffect(() => {
    fetchAnalytics();
  }, []);

  const fetchAnalytics = async () => {
    setLoading(true);
    try {
      const res = await getStudentAnalytics("student_dev_01");
      setData(res);
      if (res.mastery_per_field && res.mastery_per_field.length > 0) {
        setSelectedDomain(res.mastery_per_field[0].domain);
      }
    } catch (err) {
      console.error("Failed to load analytics dashboard:", err);
    } finally {
      setLoading(false);
    }
  };

  const kpis = data?.kpis || {
    global_mastery_avg: 0.88,
    mastery_delta_30d: 0.93,
    avg_mastery_velocity_per_min: 0.052,
    durable_retention_rate: 0.89,
    surface_memorization_drop_pct: 0.0,
  };

  // 1. Radar Chart Data for Mastery per Field
  const radarData = (data?.mastery_per_field || [
    { domain: "computer_science", mastery_score: 0.88 },
    { domain: "mathematics", mastery_score: 0.75 },
    { domain: "physics", mastery_score: 0.82 },
  ]).map((f) => ({
    subject: f.domain.replace("_", " ").toUpperCase(),
    rawDomain: f.domain,
    mastery: Math.round(f.mastery_score * 100),
    fullMark: 100,
  }));

  // 2. Bar Chart Data for Learning Style Effectiveness
  const domainTechniques: TechniqueStat[] =
    data?.learning_style_effectiveness?.[selectedDomain] ||
    data?.learning_style_effectiveness?.["computer_science"] || [
      { technique: "faded_example", avg_rating_gain: 0.22, usage_count: 6 },
      { technique: "protege", avg_rating_gain: 0.25, usage_count: 4 },
      { technique: "socratic", avg_rating_gain: 0.18, usage_count: 5 },
      { technique: "analogy", avg_rating_gain: 0.15, usage_count: 3 },
      { technique: "visual", avg_rating_gain: 0.11, usage_count: 2 },
    ];

  const barData = domainTechniques.map((t) => ({
    name: t.technique.replace("_", " "),
    gain: Math.round(t.avg_rating_gain * 100),
    count: t.usage_count,
  }));

  // 3. Composed Chart Data for Mastery Speed Timeseries
  const timeseriesData = (data?.mastery_speed_timeseries || [
    { week: "2026-W44", cumulative_mastered: 2, avg_minutes_to_mastery: 18.2 },
    { week: "2026-W45", cumulative_mastered: 5, avg_minutes_to_mastery: 14.5 },
    { week: "2026-W46", cumulative_mastered: 9, avg_minutes_to_mastery: 11.2 },
    { week: "2026-W47", cumulative_mastered: 14, avg_minutes_to_mastery: 8.4 },
  ]).map((ts) => ({
    week: ts.week,
    cumulative: ts.cumulative_mastered,
    minutes: Math.round(ts.avg_minutes_to_mastery),
  }));

  // 4. Misconceptions Vault Filter
  const rawMisconceptions = data?.lessons_learned_vault?.conquered_misconceptions || [];
  const filteredMisconceptions = rawMisconceptions.filter((m: any) => {
    if (!misconceptionFilter) return true;
    const q = misconceptionFilter.toLowerCase();
    const fb = String(m?.false_belief || "");
    const ct = String(m?.corrected_truth || "");
    return fb.toLowerCase().includes(q) || ct.toLowerCase().includes(q);
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
                <Activity className="w-5 h-5" />
              </div>
              <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-zinc-100">
                Cognitive Mastery & Learning Telemetry
              </h1>
            </div>
            <p className="text-xs text-slate-500 dark:text-zinc-400 mt-1">
              Multi-armed bandit pedagogical weights, psychometric retention curves, and longitudinal learning speed.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={fetchAnalytics}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-200 dark:border-zinc-800 text-xs font-semibold text-slate-700 dark:text-zinc-300 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
              <span>Refresh Metrics</span>
            </button>
          </div>
        </div>

        {/* Top 4 KPI Cards Strip */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* KPI 1 */}
          <div className="p-4 rounded-2xl bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 shadow-2xs space-y-1">
            <div className="flex items-center justify-between text-slate-500 dark:text-zinc-400 text-xs font-medium">
              <span>Global Mastery Index</span>
              <Award className="w-4 h-4 text-emerald-500" />
            </div>
            <div className="text-2xl font-extrabold font-mono text-slate-900 dark:text-zinc-100">
              {Math.round(kpis.global_mastery_avg * 100)}%
            </div>
            <div className="text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">
              +{Math.round(kpis.mastery_delta_30d * 100)}% gained in past 30 days
            </div>
          </div>

          {/* KPI 2 */}
          <div className="p-4 rounded-2xl bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 shadow-2xs space-y-1">
            <div className="flex items-center justify-between text-slate-500 dark:text-zinc-400 text-xs font-medium">
              <span>Mastery Velocity</span>
              <TrendingUp className="w-4 h-4 text-indigo-500" />
            </div>
            <div className="text-2xl font-extrabold font-mono text-slate-900 dark:text-zinc-100">
              +{(kpis.avg_mastery_velocity_per_min * 10).toFixed(2)}
              <span className="text-xs font-normal text-slate-400 font-sans ml-1">/ 10m</span>
            </div>
            <div className="text-[11px] text-slate-500 dark:text-zinc-400">
              Mean comprehension delta per active study minute
            </div>
          </div>

          {/* KPI 3 */}
          <div className="p-4 rounded-2xl bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 shadow-2xs space-y-1">
            <div className="flex items-center justify-between text-slate-500 dark:text-zinc-400 text-xs font-medium">
              <span>Durable Retention Rate</span>
              <ShieldCheck className="w-4 h-4 text-purple-500" />
            </div>
            <div className="text-2xl font-extrabold font-mono text-slate-900 dark:text-zinc-100">
              {Math.round(kpis.durable_retention_rate * 100)}%
            </div>
            <div className="text-[11px] text-purple-600 dark:text-purple-400 font-medium">
              Post-exam transfer vs. session mastery ratio
            </div>
          </div>

          {/* KPI 4 */}
          <div className="p-4 rounded-2xl bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 shadow-2xs space-y-1">
            <div className="flex items-center justify-between text-slate-500 dark:text-zinc-400 text-xs font-medium">
              <span>Rote Memorization Drops</span>
              <Gauge className="w-4 h-4 text-amber-500" />
            </div>
            <div className="text-2xl font-extrabold font-mono text-slate-900 dark:text-zinc-100">
              {kpis.surface_memorization_drop_pct.toFixed(1)}%
            </div>
            <div className="text-[11px] text-slate-500 dark:text-zinc-400">
              Prosody monotone flagged turns requiring Socratic depth
            </div>
          </div>
        </div>

        {/* Bento Grid: Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Chart 1: Mastery Per Field Radar */}
          <div className="p-5 rounded-2xl bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 shadow-2xs space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
                  <Compass className="w-4 h-4 text-indigo-500" />
                  Academic Domain Mastery
                </h3>
                <p className="text-[11px] text-slate-500 dark:text-zinc-400">
                  Click a domain to inspect its multi-armed bandit technique weights.
                </p>
              </div>
            </div>

            <div className="h-64 w-full flex items-center justify-center">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={radarData}>
                  <PolarGrid stroke="#64748b" strokeOpacity={0.2} />
                  <PolarAngleAxis
                    dataKey="subject"
                    tick={{ fill: "#64748b", fontSize: 11 }}
                    onClick={(e) => {
                      const matched = radarData.find((r) => r.subject === e.value);
                      if (matched) setSelectedDomain(matched.rawDomain);
                    }}
                  />
                  <PolarRadiusAxis angle={30} domain={[0, 100]} stroke="#64748b" strokeOpacity={0.3} />
                  <Radar
                    name="Mastery %"
                    dataKey="mastery"
                    stroke="#6366f1"
                    fill="#6366f1"
                    fillOpacity={0.4}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#18181b",
                      borderColor: "#27272a",
                      borderRadius: "12px",
                      fontSize: "12px",
                      color: "#f4f4f5",
                    }}
                  />
                </RadarChart>
              </ResponsiveContainer>
            </div>

            {/* Quick Domain Filter Chips */}
            <div className="flex items-center gap-1.5 flex-wrap pt-1">
              {radarData.map((d) => (
                <button
                  key={d.rawDomain}
                  onClick={() => setSelectedDomain(d.rawDomain)}
                  className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
                    selectedDomain === d.rawDomain
                      ? "bg-indigo-600 text-white shadow-2xs"
                      : "bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-zinc-400 hover:bg-slate-200"
                  }`}
                >
                  {d.subject} ({d.mastery}%)
                </button>
              ))}
            </div>
          </div>

          {/* Chart 2: Best Learning Style by Field */}
          <div className="p-5 rounded-2xl bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 shadow-2xs space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
                  <Zap className="w-4 h-4 text-purple-500" />
                  Technique Effectiveness • {selectedDomain.replace("_", " ").toUpperCase()}
                </h3>
                <p className="text-[11px] text-slate-500 dark:text-zinc-400">
                  Average comprehension gain (+rating / turn) reinforced by bandit weights.
                </p>
              </div>
            </div>

            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={barData} layout="vertical" margin={{ top: 10, right: 20, left: 20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#64748b" strokeOpacity={0.15} />
                  <XAxis type="number" unit="%" stroke="#64748b" fontSize={11} domain={[0, 35]} />
                  <YAxis type="category" dataKey="name" stroke="#64748b" fontSize={11} width={90} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#18181b",
                      borderColor: "#27272a",
                      borderRadius: "12px",
                      fontSize: "12px",
                      color: "#f4f4f5",
                    }}
                    formatter={(val) => [`+${val}% average gain per turn`, "Technique Reward"]}
                  />
                  <Bar dataKey="gain" fill="#8b5cf6" radius={[0, 6, 6, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Chart 3: Mastery Speed Over Time */}
        <div className="p-5 rounded-2xl bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 shadow-2xs space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
                <Clock className="w-4 h-4 text-emerald-500" />
                Longitudinal Mastery Speed & Learning Curve
              </h3>
              <p className="text-[11px] text-slate-500 dark:text-zinc-400">
                Cumulative concepts mastered (Area) vs. decreasing minutes-to-mastery (Line).
              </p>
            </div>
          </div>

          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={timeseriesData} margin={{ top: 15, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#64748b" strokeOpacity={0.15} />
                <XAxis dataKey="week" stroke="#64748b" fontSize={11} />
                <YAxis yAxisId="left" stroke="#10b981" fontSize={11} label={{ value: "Mastered Nodes", angle: -90, position: "insideLeft", fill: "#10b981", fontSize: 10 }} />
                <YAxis yAxisId="right" orientation="right" stroke="#f59e0b" fontSize={11} label={{ value: "Minutes / Concept", angle: 90, position: "insideRight", fill: "#f59e0b", fontSize: 10 }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#18181b",
                    borderColor: "#27272a",
                    borderRadius: "12px",
                    fontSize: "12px",
                    color: "#f4f4f5",
                  }}
                />
                <Legend wrapperStyle={{ fontSize: "11px", paddingTop: "8px" }} />
                <Area yAxisId="left" type="monotone" dataKey="cumulative" name="Cumulative Concepts" fill="#10b981" fillOpacity={0.18} stroke="#10b981" strokeWidth={2} />
                <Line yAxisId="right" type="monotone" dataKey="minutes" name="Avg Minutes to Mastery" stroke="#f59e0b" strokeWidth={2.5} dot={{ r: 4 }} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Section 4: Lessons Learned & Misconception Vault */}
        <div className="p-5 rounded-2xl bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 shadow-2xs space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                Misconception Repair Vault
              </h3>
              <p className="text-[11px] text-slate-500 dark:text-zinc-400">
                Cognitive fallacies diagnosed through Socratic traps and corrected via counter-example verification.
              </p>
            </div>

            <div className="relative min-w-[200px]">
              <Search className="absolute left-3 top-2.5 w-3.5 h-3.5 text-slate-400" />
              <input
                type="text"
                placeholder="Filter repaired traps..."
                value={misconceptionFilter}
                onChange={(e) => setMisconceptionFilter(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 rounded-xl text-xs bg-slate-50 dark:bg-zinc-850 border border-slate-200 dark:border-zinc-700/60 text-slate-900 dark:text-zinc-100 placeholder:text-slate-400 focus:outline-hidden focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          </div>

          {filteredMisconceptions.length === 0 ? (
            <div className="p-8 text-center rounded-xl border border-dashed border-slate-200 dark:border-zinc-800 text-xs text-slate-500 dark:text-zinc-400">
              <Sparkles className="w-6 h-6 text-slate-400 mx-auto mb-2" />
              <p>No misconceptions currently flagged in this view.</p>
              <p className="text-[10px] text-slate-400 mt-1">Traps diagnosed during active sessions will automatically persist here.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {filteredMisconceptions.map((item, idx) => (
                <div
                  key={idx}
                  className="p-3.5 rounded-xl border border-slate-200 dark:border-zinc-800 bg-slate-50/60 dark:bg-zinc-850/40 text-xs space-y-1.5"
                >
                  <div className="text-[11px] font-mono text-rose-600 dark:text-rose-400 line-through">
                    What You Thought: {String((item as any)?.false_belief || "")}
                  </div>
                  <div className="text-[11px] font-medium text-emerald-600 dark:text-emerald-400 flex items-start gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5 flex-shrink-0 mt-0.5 text-emerald-500" />
                    <span>Verified Mental Model: {String((item as any)?.corrected_truth || "")}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
