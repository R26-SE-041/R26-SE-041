"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getAnalyticsReport } from "@/lib/api";
import type { AnalyticsReport } from "@/types/quiz";

// ── Score ring SVG ──────────────────────────────────────────────
function ScoreRing({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (pct / 100) * circumference;
  const color = pct >= 70 ? "#34d399" : pct >= 50 ? "#fbbf24" : "#f87171";
  const grade = pct >= 90 ? "A+" : pct >= 80 ? "A" : pct >= 70 ? "B" : pct >= 60 ? "C" : "D";

  return (
    <div className="relative flex items-center justify-center">
      <svg width="140" height="140" className="rotate-[-90deg]">
        <circle cx="70" cy="70" r={radius} fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="10" />
        <circle
          cx="70"
          cy="70"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 1.5s ease-out", filter: `drop-shadow(0 0 12px ${color}60)` }}
        />
      </svg>
      <div className="absolute text-center">
        <p className="text-4xl font-extrabold" style={{ color }}>{pct}%</p>
        <p className="text-sm font-bold text-white/50">Grade {grade}</p>
      </div>
    </div>
  );
}

// ── Topic bar chart ─────────────────────────────────────────────
function TopicBar({ topic, correct, total }: { topic: string; correct: number; total: number }) {
  const pct = total > 0 ? (correct / total) * 100 : 0;
  const color = pct >= 70 ? "#34d399" : pct >= 50 ? "#fbbf24" : "#f87171";
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm text-white/70 truncate max-w-[60%]">{topic}</span>
        <span className="text-sm font-bold" style={{ color }}>
          {correct}/{total} ({Math.round(pct)}%)
        </span>
      </div>
      <div className="h-2 rounded-full bg-white/10 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-1000"
          style={{ width: `${pct}%`, background: color, boxShadow: `0 0 8px ${color}60` }}
        />
      </div>
    </div>
  );
}

// ── Bloom heatmap ───────────────────────────────────────────────
const BLOOM_COLORS: Record<string, string> = {
  remember: "#818cf8",
  understand: "#a78bfa",
  apply: "#7c3aed",
  analyze: "#06b6d4",
  evaluate: "#0891b2",
  create: "#0e7490",
};

// ── Loading skeleton ────────────────────────────────────────────
function Skeleton() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <div className="w-20 h-20 rounded-full border-4 border-violet-500/30 border-t-violet-500 animate-spin mx-auto mb-4" />
        <p className="text-white/50">Loading your results...</p>
      </div>
    </div>
  );
}

export default function ResultsPage() {
  const params = useParams();
  const sessionId = params.sessionId as string;
  const [report, setReport] = useState<AnalyticsReport | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getAnalyticsReport(sessionId)
      .then(setReport)
      .catch((e) => setError(e.message));
  }, [sessionId]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="text-center">
          <p className="text-6xl mb-4">⚠️</p>
          <h1 className="text-2xl font-bold text-white mb-2">Could not load results</h1>
          <p className="text-white/50 mb-6">{error}</p>
          <Link href="/" className="btn-secondary">Back to Home</Link>
        </div>
      </div>
    );
  }

  if (!report) return <Skeleton />;

  const topicEntries = Object.entries(report.topic_scores || {});
  const bloomEntries = Object.entries(report.bloom_scores || {});
  const finalPct = Math.round(report.final_score * 100);

  return (
    <main className="min-h-screen py-12 px-4">
      {/* Nav */}
      <nav className="flex items-center justify-between max-w-5xl mx-auto mb-12">
        <Link href="/" className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: "linear-gradient(135deg, #7c3aed, #4f46e5)" }}>
            <span className="text-white font-bold text-xs">AQ</span>
          </div>
          <span className="font-bold text-base text-white">AdaptiveIQ</span>
        </Link>
        <Link href="/upload" id="btn-new-quiz" className="text-sm text-violet-400 hover:text-violet-300 transition-colors font-semibold">
          New Quiz →
        </Link>
      </nav>

      <div className="max-w-5xl mx-auto animate-[fadeIn_0.5s_ease-out]">
        <h1 className="text-4xl font-extrabold text-white mb-2 tracking-tight">Quiz Complete! 🎓</h1>
        <p className="text-white/50 text-lg mb-10">
          You answered {report.correct_count} out of {report.total_questions} questions correctly.
        </p>

        {/* Top row: score + quick stats */}
        <div className="grid md:grid-cols-3 gap-5 mb-6">
          {/* Score ring */}
          <div className="rounded-2xl p-6 border border-white/10 bg-white/5 backdrop-blur-sm flex flex-col items-center justify-center">
            <ScoreRing score={report.final_score} />
            <p className="mt-4 text-white/50 text-sm">Final Score</p>
          </div>

          {/* Quick stats */}
          <div className="md:col-span-2 grid grid-cols-2 gap-4">
            {[
              { icon: "✅", label: "Correct", val: report.correct_count, color: "#34d399" },
              { icon: "❌", label: "Incorrect", val: report.total_questions - report.correct_count, color: "#f87171" },
              {
                icon: "⏱️",
                label: "Avg Time/Q",
                val: `${Math.round(report.avg_time_per_question)}s`,
                color: "#fbbf24",
              },
              {
                icon: "🎯",
                label: "Grounding Score",
                val: `${Math.round((report.grounding_stats?.avg_grounding_score ?? 0) * 100)}%`,
                color: "#818cf8",
              },
            ].map((s) => (
              <div
                key={s.label}
                className="rounded-xl p-5 border border-white/10 bg-white/5 backdrop-blur-sm"
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xl">{s.icon}</span>
                  <span className="text-xs text-white/40 font-semibold uppercase tracking-wide">{s.label}</span>
                </div>
                <p className="text-3xl font-extrabold" style={{ color: s.color }}>{s.val}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Weak / Strong topics */}
        {(report.weak_topics?.length > 0 || report.strong_topics?.length > 0) && (
          <div className="grid md:grid-cols-2 gap-5 mb-6">
            {report.strong_topics?.length > 0 && (
              <div className="rounded-2xl p-6 border border-emerald-500/20 bg-emerald-500/5">
                <h2 className="font-bold text-emerald-300 mb-4 flex items-center gap-2">
                  💪 Strong Topics
                </h2>
                <div className="flex flex-wrap gap-2">
                  {report.strong_topics.map((t) => (
                    <span key={t} className="px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-500/25">{t}</span>
                  ))}
                </div>
              </div>
            )}
            {report.weak_topics?.length > 0 && (
              <div className="rounded-2xl p-6 border border-red-500/20 bg-red-500/5">
                <h2 className="font-bold text-red-300 mb-4 flex items-center gap-2">
                  📚 Needs Review
                </h2>
                <div className="flex flex-wrap gap-2">
                  {report.weak_topics.map((t) => (
                    <span key={t} className="px-3 py-1 rounded-full text-xs font-semibold bg-red-500/15 text-red-300 border border-red-500/25">{t}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Topic performance */}
        {topicEntries.length > 0 && (
          <div className="rounded-2xl p-6 border border-white/10 bg-white/5 backdrop-blur-sm mb-5">
            <h2 className="font-bold text-white text-lg mb-5">📊 Topic Performance</h2>
            <div className="space-y-4">
              {topicEntries.map(([topic, { correct, total }]) => (
                <TopicBar key={topic} topic={topic} correct={correct} total={total} />
              ))}
            </div>
          </div>
        )}

        {/* Bloom's distribution */}
        {bloomEntries.length > 0 && (
          <div className="rounded-2xl p-6 border border-white/10 bg-white/5 backdrop-blur-sm mb-5">
            <h2 className="font-bold text-white text-lg mb-5">🌿 Bloom&apos;s Taxonomy Coverage</h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {bloomEntries.map(([level, { correct, total }]) => {
                const pct = total > 0 ? Math.round((correct / total) * 100) : 0;
                const color = BLOOM_COLORS[level] ?? "#818cf8";
                return (
                  <div
                    key={level}
                    className="rounded-xl p-4 border"
                    style={{ borderColor: `${color}30`, background: `${color}0f` }}
                  >
                    <p className="text-xs font-semibold capitalize mb-1" style={{ color }}>{level}</p>
                    <p className="text-2xl font-extrabold text-white">{pct}%</p>
                    <p className="text-xs text-white/40">{correct}/{total} correct</p>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Difficulty progression */}
        {report.difficulty_progression?.length > 1 && (
          <div className="rounded-2xl p-6 border border-white/10 bg-white/5 backdrop-blur-sm mb-8">
            <h2 className="font-bold text-white text-lg mb-4">📈 Adaptive Difficulty Progression</h2>
            <div className="flex items-end gap-1.5 h-16">
              {report.difficulty_progression.map((d, i) => {
                const color = d < 0.33 ? "#34d399" : d < 0.66 ? "#fbbf24" : "#f87171";
                return (
                  <div key={i} className="flex-1 rounded-sm transition-all duration-700" style={{ height: `${d * 100}%`, background: color, opacity: 0.8 }} title={`Q${i + 1}: ${Math.round(d * 100)}%`} />
                );
              })}
            </div>
            <div className="flex justify-between text-xs text-white/30 mt-2">
              <span>Q1</span>
              <span>Easy → Medium → Hard</span>
              <span>Q{report.difficulty_progression.length}</span>
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex flex-col sm:flex-row gap-4">
          <Link
            href="/upload"
            id="btn-retake-quiz"
            className="flex-1 py-4 rounded-xl font-bold text-white text-center transition-all duration-200"
            style={{ background: "linear-gradient(135deg, #7c3aed, #4f46e5)", boxShadow: "0 4px 20px rgba(124,58,237,0.35)" }}
          >
            Take Another Quiz →
          </Link>
          <button
            id="btn-export-results"
            onClick={() => {
              const data = JSON.stringify(report, null, 2);
              const blob = new Blob([data], { type: "application/json" });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = `quiz-results-${sessionId.slice(0, 8)}.json`;
              a.click();
            }}
            className="flex-1 py-4 rounded-xl font-bold border border-white/15 bg-white/5 text-white/70 hover:text-white hover:bg-white/10 transition-all duration-200 text-center"
          >
            Export Results (JSON)
          </button>
        </div>

        {/* Session ID for research */}
        <p className="text-center text-white/20 text-xs mt-6 font-mono">
          Session ID: {sessionId} · Grounding avg: {Math.round((report.grounding_stats?.avg_grounding_score ?? 0) * 100)}%
        </p>
      </div>
    </main>
  );
}
