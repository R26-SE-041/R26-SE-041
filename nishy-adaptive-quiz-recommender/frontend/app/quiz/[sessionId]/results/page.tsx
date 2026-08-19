"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getAnalyticsReport } from "@/lib/api";
import type {
  AnalyticsReport,
  WeakTopicRecommendation,
  QuestionMarkDetail,
  ResourceLink,
} from "@/types/quiz";
import {
  CheckIcon,
  XIcon,
  AlertTriangleIcon,
  BookOpenIcon,
  LinkIcon,
  ClipboardIcon,
  ZapIcon,
  BarChartIcon,
  TargetIcon,
  RefreshIcon,
  LightbulbIcon,
  ChevronDownIcon,
  NoteIcon,
  PlayIcon,
  StarIcon,
} from "@/components/ui/Icons";

// ── Helpers ──────────────────────────────────────────────────────
function gradeFromScore(score: number): { grade: string; color: string; glow: string } {
  if (score >= 85) return { grade: "A+", color: "#34d399", glow: "rgba(52,211,153,0.35)" };
  if (score >= 80) return { grade: "A",  color: "#34d399", glow: "rgba(52,211,153,0.25)" };
  if (score >= 75) return { grade: "A-", color: "#34d399", glow: "rgba(52,211,153,0.25)" };
  if (score >= 70) return { grade: "B+", color: "#fbbf24", glow: "rgba(251,191,36,0.25)" };
  if (score >= 65) return { grade: "B",  color: "#fbbf24", glow: "rgba(251,191,36,0.25)" };
  if (score >= 60) return { grade: "B-", color: "#fbbf24", glow: "rgba(251,191,36,0.25)" };
  if (score >= 55) return { grade: "C+", color: "#f97316", glow: "rgba(249,115,22,0.25)" };
  if (score >= 50) return { grade: "C",  color: "#f97316", glow: "rgba(249,115,22,0.25)" };
  if (score >= 45) return { grade: "C-", color: "#f97316", glow: "rgba(249,115,22,0.25)" };
  if (score >= 40) return { grade: "D+", color: "#f87171", glow: "rgba(248,113,113,0.25)" };
  if (score >= 35) return { grade: "D",  color: "#f87171", glow: "rgba(248,113,113,0.25)" };
  return            { grade: "E",  color: "#ef4444", glow: "rgba(239,68,68,0.25)" };
}

function attemptsLabel(attempts: number, isCorrect: boolean): string {
  if (!isCorrect) return "Wrong";
  if (attempts === 1) return "1st try";
  if (attempts === 2) return "2nd try";
  if (attempts === 3) return "3rd try";
  return "4th try";
}

const LANG_COLORS: Record<string, { bg: string; border: string; text: string; dot: string }> = {
  English: { bg: "rgba(99,102,241,0.12)", border: "rgba(99,102,241,0.3)", text: "#a5b4fc", dot: "#6366f1" },
  Tamil:   { bg: "rgba(236,72,153,0.10)", border: "rgba(236,72,153,0.3)", text: "#f9a8d4", dot: "#ec4899" },
  Sinhala: { bg: "rgba(16,185,129,0.10)", border: "rgba(16,185,129,0.3)", text: "#6ee7b7", dot: "#10b981" },
};

function getLangStyle(label: string) {
  return LANG_COLORS[label] ?? LANG_COLORS.English;
}

// ── Source icon — SVG per provider ───────────────────────────────
function SourceIcon({ source }: { source: string }) {
  if (source === "YouTube")
    return <PlayIcon className="w-4 h-4" />;
  if (source === "GeeksforGeeks")
    return <ZapIcon className="w-4 h-4" />;
  return <BookOpenIcon className="w-4 h-4" />;
}

// ── Score Ring ────────────────────────────────────────────────────
function ScoreRing({ score }: { score: number }) {
  const pct = Math.round(score);
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (pct / 100) * circumference;
  const { grade, color, glow } = gradeFromScore(pct);
  return (
    <div className="relative flex items-center justify-center">
      <svg width="148" height="148" className="rotate-[-90deg]">
        <circle cx="74" cy="74" r={radius} fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="12" />
        <circle
          cx="74" cy="74" r={radius} fill="none"
          stroke={color} strokeWidth="12" strokeLinecap="round"
          strokeDasharray={circumference} strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 1.5s ease-out", filter: `drop-shadow(0 0 14px ${glow})` }}
        />
      </svg>
      <div className="absolute text-center">
        <p className="text-4xl font-extrabold" style={{ color }}>{pct}%</p>
        <p className="text-sm font-black tracking-widest" style={{ color }}>{grade}</p>
      </div>
    </div>
  );
}

// ── Marks Badge per attempt ───────────────────────────────────────
function MarksBadge({ marks }: { marks: number }) {
  const color =
    marks === 100 ? "#34d399"
    : marks === 75  ? "#fbbf24"
    : marks === 50  ? "#f97316"
    : marks === 25  ? "#a78bfa"
    : "#f87171";
  return (
    <span
      className="inline-flex items-center justify-center w-12 h-8 rounded-lg text-xs font-black"
      style={{ background: `${color}20`, color, border: `1px solid ${color}40` }}
    >
      {marks}
    </span>
  );
}

// ── Resource Link Card ────────────────────────────────────────────
function ResourceCard({ resource }: { resource: ResourceLink }) {
  const style = getLangStyle(resource.label);
  return (
    <a
      href={resource.url}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center gap-3 px-4 py-3 rounded-xl border transition-all duration-200 hover:scale-[1.02] hover:brightness-110 group"
      style={{ background: style.bg, borderColor: style.border }}
    >
      <span className="shrink-0" style={{ color: style.text }}>
        <SourceIcon source={resource.source} />
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-bold truncate" style={{ color: style.text }}>{resource.title}</p>
        <p className="text-xs text-white/30 mt-0.5">{resource.source}</p>
      </div>
      <span
        className="shrink-0 text-xs font-bold px-2 py-0.5 rounded-full flex items-center gap-1"
        style={{ background: `${style.dot}20`, color: style.text }}
      >
        <span className="w-1.5 h-1.5 rounded-full inline-block" style={{ background: style.dot }} />
        {resource.label}
      </span>
    </a>
  );
}

// ── Weak Topic Card ───────────────────────────────────────────────
function WeakTopicCard({ rec }: { rec: WeakTopicRecommendation }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div
      className="rounded-2xl border overflow-hidden"
      style={{ background: "rgba(239,68,68,0.05)", borderColor: "rgba(239,68,68,0.18)" }}
    >
      {/* Header */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-6 py-4 text-left transition-colors duration-150 hover:bg-white/5"
      >
        <div className="flex items-center gap-3">
          <span className="text-red-400/70">
            <BookOpenIcon className="w-5 h-5" />
          </span>
          <div>
            <p className="text-white font-bold text-base">{rec.topic}</p>
            <p className="text-red-400 text-xs font-semibold mt-0.5">
              {rec.percentage}% correct — needs review
            </p>
          </div>
        </div>
        <span
          className="text-white/40 transition-transform duration-200"
          style={{ transform: expanded ? "rotate(180deg)" : "" }}
        >
          <ChevronDownIcon className="w-5 h-5" />
        </span>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="px-6 pb-6 border-t border-red-500/10 pt-5 animate-[fadeIn_0.2s_ease-out]">

          {/* Concept Notes */}
          {rec.concept_notes && rec.concept_notes.length > 0 && (
            <div className="mb-5">
              <div className="flex items-center gap-2 mb-3">
                <div
                  className="w-5 h-5 rounded flex items-center justify-center"
                  style={{ background: "rgba(139,92,246,0.2)", color: "#c4b5fd" }}
                >
                  <NoteIcon className="w-3 h-3" />
                </div>
                <p className="text-xs font-bold uppercase tracking-widest text-white/40">Concept Notes</p>
              </div>
              <div
                className="rounded-xl p-4 space-y-2.5"
                style={{ background: "rgba(139,92,246,0.07)", border: "1px solid rgba(139,92,246,0.15)" }}
              >
                {rec.concept_notes.map((note, i) => {
                  // Bold the part before the first colon if it starts with **...**
                  const formatted = note.replace(/\*\*(.+?)\*\*/g, '<strong class="text-violet-300">$1</strong>');
                  return (
                    <div key={i} className="flex gap-2.5 text-sm leading-relaxed text-white/75">
                      <span className="text-violet-400 mt-0.5 shrink-0">•</span>
                      <span dangerouslySetInnerHTML={{ __html: formatted }} />
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Resource Links */}
          {rec.resources && rec.resources.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <div
                  className="w-5 h-5 rounded flex items-center justify-center"
                  style={{ background: "rgba(6,182,212,0.15)", color: "#67e8f9" }}
                >
                  <LinkIcon className="w-3 h-3" />
                </div>
                <p className="text-xs font-bold uppercase tracking-widest text-white/40">Learning Resources</p>
              </div>
              <div className="space-y-2">
                {rec.resources.map((r, i) => (
                  <ResourceCard key={i} resource={r} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Question Breakdown Row ─────────────────────────────────────────
function QMarkRow({ qm }: { qm: QuestionMarkDetail }) {
  const diffColor = qm.difficulty < 0.33 ? "#34d399" : qm.difficulty < 0.66 ? "#fbbf24" : "#f87171";
  const diffLabel = qm.difficulty < 0.33 ? "Easy" : qm.difficulty < 0.66 ? "Medium" : "Hard";
  return (
    <tr className="border-t border-white/5 hover:bg-white/[0.025] transition-colors">
      <td className="py-3 px-4 text-white/50 text-sm font-mono">Q{qm.q_num}</td>
      <td className="py-3 px-4 text-white/70 text-sm max-w-[180px] truncate">{qm.topic}</td>
      <td className="py-3 px-4">
        <span
          className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-semibold"
          style={{ color: diffColor, background: `${diffColor}15`, border: `1px solid ${diffColor}30` }}
        >
          {diffLabel}
        </span>
      </td>
      <td className="py-3 px-4 text-sm text-center">
        <span
          className="inline-flex items-center gap-1"
          style={{ color: qm.is_correct ? "#34d399" : "#f87171" }}
        >
          {qm.is_correct
            ? <CheckIcon className="w-3.5 h-3.5" />
            : <XIcon className="w-3.5 h-3.5" />}
          {attemptsLabel(qm.attempts, qm.is_correct)}
        </span>
      </td>
      <td className="py-3 px-4 text-center">
        <span className="text-white/40 text-xs">{qm.hints_used}</span>
      </td>
      <td className="py-3 px-4 text-center">
        <MarksBadge marks={qm.marks} />
      </td>
    </tr>
  );
}

// ── Topic Performance Bar ─────────────────────────────────────────
function TopicBar({ topic, correct, total }: { topic: string; correct: number; total: number }) {
  const pct = total > 0 ? Math.round((correct / total) * 100) : 0;
  const color = pct >= 70 ? "#34d399" : pct >= 50 ? "#fbbf24" : "#f87171";
  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-sm text-white/70 truncate max-w-[60%]">{topic}</span>
        <span className="text-sm font-bold" style={{ color }}>{correct}/{total} ({pct}%)</span>
      </div>
      <div className="h-2 rounded-full bg-white/10 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-1000"
          style={{ width: `${pct}%`, background: color, boxShadow: `0 0 8px ${color}50` }}
        />
      </div>
    </div>
  );
}

// ── Loading Skeleton ──────────────────────────────────────────────
function Skeleton() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <div className="w-20 h-20 rounded-full border-4 border-violet-500/30 border-t-violet-500 animate-spin mx-auto mb-4" />
        <p className="text-white/50">Generating your performance report...</p>
        <p className="text-white/30 text-sm mt-1">Analysing weak areas &amp; preparing study notes</p>
      </div>
    </div>
  );
}

// ── Marks Scoring Legend ──────────────────────────────────────────
function MarksLegend() {
  const items = [
    { marks: 100, label: "1st attempt" },
    { marks: 75,  label: "2nd attempt" },
    { marks: 50,  label: "3rd attempt" },
    { marks: 25,  label: "4th attempt" },
    { marks: 0,   label: "Not answered" },
  ];
  return (
    <div
      className="rounded-xl px-5 py-4 mb-6 flex flex-wrap gap-3 items-center"
      style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)" }}
    >
      <span className="text-xs font-bold uppercase tracking-widest text-white/30 mr-2">Marks Scheme</span>
      {items.map((item) => (
        <div key={item.marks} className="flex items-center gap-1.5">
          <MarksBadge marks={item.marks} />
          <span className="text-xs text-white/40">{item.label}</span>
        </div>
      ))}
    </div>
  );
}

// ── Main Results Page ─────────────────────────────────────────────
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
          <div className="flex justify-center mb-4">
            <AlertTriangleIcon className="w-16 h-16 text-amber-400" />
          </div>
          <h1 className="text-2xl font-bold text-white mb-2">Could not load results</h1>
          <p className="text-white/50 mb-6">{error}</p>
          <Link href="/" className="inline-block px-6 py-3 rounded-xl font-bold text-white"
            style={{ background: "linear-gradient(135deg, #7c3aed, #4f46e5)" }}>
            Back to Home
          </Link>
        </div>
      </div>
    );
  }

  if (!report) return <Skeleton />;

  const topicEntries = Object.entries(report.topic_scores || {});
  const finalPct = Math.round(report.final_score);
  const { grade, color: gradeColor } = gradeFromScore(finalPct);
  const marksEarned = report.total_marks_earned ?? 0;
  const marksPossible = report.total_marks_possible ?? (report.total_questions * 100);
  const correctCount = report.correct_count ?? topicEntries.reduce((s, [, v]) => s + v.correct, 0);
  const weakRecs = (report.recommendations ?? []).filter((r) => r.concept_notes && r.resources);

  const stats = [
    { icon: <CheckIcon className="w-5 h-5" />,      label: "Correct",      val: `${correctCount} / ${report.total_questions}`, color: "#34d399" },
    { icon: <TargetIcon className="w-5 h-5" />,     label: "Grade",        val: grade,                                          color: gradeColor },
    { icon: <LightbulbIcon className="w-5 h-5" />,  label: "Hints Used",   val: String(
        (report.question_marks_detail ?? []).reduce((s, q) => s + q.hints_used, 0)
      ),                                                                                          color: "#a78bfa" },
  ];

  return (
    <main className="min-h-screen py-10 px-4">
      {/* Nav */}
      <nav className="flex items-center justify-between max-w-5xl mx-auto mb-10">
        <Link href="/" className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center"
            style={{ background: "linear-gradient(135deg, #7c3aed, #4f46e5)" }}>
            <span className="text-white font-bold text-xs">AQ</span>
          </div>
          <span className="font-bold text-base text-white">AdaptiveIQ</span>
        </Link>
        <Link href="/upload" id="btn-new-quiz"
          className="text-sm text-violet-400 hover:text-violet-300 transition-colors font-semibold">
          New Quiz →
        </Link>
      </nav>

      <div className="max-w-5xl mx-auto animate-[fadeIn_0.5s_ease-out]">

        {/* ── Page Title ── */}
        <h1 className="text-4xl font-extrabold text-white mb-1 tracking-tight">Quiz Complete</h1>
        <p className="text-white/40 text-base mb-8">
          Here&apos;s your full performance breakdown — marks, weak concepts, and study resources.
        </p>

        {/* ── Score + Stats Row ── */}
        <div className="grid md:grid-cols-3 gap-5 mb-6">
          {/* Score ring */}
          <div
            className="rounded-2xl p-6 border flex flex-col items-center justify-center gap-3"
            style={{ background: "rgba(255,255,255,0.04)", borderColor: "rgba(255,255,255,0.1)", backdropFilter: "blur(12px)" }}
          >
            <ScoreRing score={finalPct} />
            <div className="text-center">
              <p className="text-white font-bold text-lg">
                {marksEarned} / {marksPossible} marks
              </p>
              <p className="text-white/40 text-xs mt-0.5">Attempt-weighted score</p>
            </div>
          </div>

          {/* Quick stats row */}
          <div className="md:col-span-2 grid grid-cols-1 sm:grid-cols-3 gap-4">
            {stats.map((s) => (
              <div
                key={s.label}
                className="rounded-xl p-5 border"
                style={{ background: "rgba(255,255,255,0.04)", borderColor: "rgba(255,255,255,0.1)", backdropFilter: "blur(12px)" }}
              >
                <div className="flex items-center gap-2 mb-2">
                  <span style={{ color: s.color }}>{s.icon}</span>
                  <span className="text-xs text-white/40 font-semibold uppercase tracking-wide">{s.label}</span>
                </div>
                <p className="text-3xl font-extrabold" style={{ color: s.color }}>{s.val}</p>
              </div>
            ))}
          </div>
        </div>

        {/* ── Marks Breakdown Table ── */}
        {report.question_marks_detail && report.question_marks_detail.length > 0 && (
          <div
            className="rounded-2xl border mb-6 overflow-hidden"
            style={{ background: "rgba(255,255,255,0.03)", borderColor: "rgba(255,255,255,0.09)", backdropFilter: "blur(12px)" }}
          >
            <div className="px-6 pt-5 pb-3 flex items-center gap-2">
              <span className="text-white/60">
                <ClipboardIcon className="w-5 h-5" />
              </span>
              <h2 className="font-bold text-white text-lg">Marks Breakdown</h2>
              <span className="ml-auto text-xs text-white/30">Out of 100 per question</span>
            </div>
            <MarksLegend />
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-t border-white/10">
                    {["Q", "Topic", "Difficulty", "Result", "Hints", "Marks"].map((h) => (
                      <th key={h} className="py-2.5 px-4 text-xs font-bold uppercase tracking-widest text-white/25">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {report.question_marks_detail.map((qm) => (
                    <QMarkRow key={qm.q_num} qm={qm} />
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t border-white/10 bg-white/[0.025]">
                    <td colSpan={5} className="py-3 px-4 text-sm font-bold text-white/60 text-right">Total Marks</td>
                    <td className="py-3 px-4 text-center">
                      <span className="text-lg font-extrabold" style={{ color: gradeColor }}>
                        {marksEarned} / {marksPossible}
                      </span>
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
        )}

        {/* ── Weak Areas Study Notes ── */}
        {weakRecs.length > 0 && (
          <div className="mb-6">
            <div className="flex items-center gap-2 mb-4">
              <span className="text-violet-400">
                <ZapIcon className="w-6 h-6" />
              </span>
              <h2 className="font-bold text-white text-xl">Weak Areas — Study Notes</h2>
            </div>
            <p className="text-white/40 text-sm mb-5">
              Click each topic to expand concept notes from your study material + curated learning resources.
            </p>
            <div className="space-y-3">
              {weakRecs.map((rec, i) => (
                <WeakTopicCard key={i} rec={rec} />
              ))}
            </div>
          </div>
        )}


        {/* ── Topic Performance Bars ── */}
        {topicEntries.length > 0 && (
          <div
            className="rounded-2xl p-6 border mb-5"
            style={{ background: "rgba(255,255,255,0.04)", borderColor: "rgba(255,255,255,0.09)", backdropFilter: "blur(12px)" }}
          >
            <h2 className="font-bold text-white text-lg mb-5 flex items-center gap-2">
              <span className="text-white/60"><BarChartIcon className="w-5 h-5" /></span>
              Topic Performance
            </h2>
            <div className="space-y-4">
              {topicEntries.map(([topic, { correct, total }]) => (
                <TopicBar key={topic} topic={topic} correct={correct} total={total} />
              ))}
            </div>
          </div>
        )}

        {/* ── Actions ── */}
        <div className="flex flex-col sm:flex-row gap-4">
          <Link href="/upload" id="btn-retake-quiz"
            className="flex-1 py-4 rounded-xl font-bold text-white text-center transition-all duration-200"
            style={{ background: "linear-gradient(135deg, #7c3aed, #4f46e5)", boxShadow: "0 4px 20px rgba(124,58,237,0.35)" }}>
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

        <p className="text-center text-white/20 text-xs mt-6 font-mono">
          Session: {sessionId} · Grounding avg: {Math.round((report.grounding_stats?.avg_grounding_score ?? 0) * 100)}%
        </p>
      </div>
    </main>
  );
}
