"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getAnalyticsReport, submitFeedback } from "@/lib/api";
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
  ArrowRightIcon,
} from "@/components/ui/Icons";

// ── Star-fill icon (solid) used for filled rating stars ─────────────
function StarFillIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className={className}>
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  );
}

// ── Helpers ──────────────────────────────────────────────────────
function gradeFromScore(score: number): { grade: string; color: string; glow: string } {
  if (score >= 85) return { grade: "A+", color: "var(--success)", glow: "var(--shadow)" };
  if (score >= 80) return { grade: "A", color: "var(--success)", glow: "var(--shadow)" };
  if (score >= 75) return { grade: "A-", color: "var(--success)", glow: "var(--shadow)" };
  if (score >= 70) return { grade: "B+", color: "var(--warning)", glow: "var(--shadow)" };
  if (score >= 65) return { grade: "B", color: "var(--warning)", glow: "var(--shadow)" };
  if (score >= 60) return { grade: "B-", color: "var(--warning)", glow: "var(--shadow)" };
  if (score >= 55) return { grade: "C+", color: "var(--primary)", glow: "var(--shadow)" };
  if (score >= 50) return { grade: "C", color: "var(--primary)", glow: "var(--shadow)" };
  if (score >= 45) return { grade: "C-", color: "var(--primary)", glow: "var(--shadow)" };
  if (score >= 40) return { grade: "D+", color: "var(--danger)", glow: "var(--shadow)" };
  if (score >= 35) return { grade: "D", color: "var(--danger)", glow: "var(--shadow)" };
  return { grade: "E", color: "var(--danger)", glow: "var(--shadow)" };
}

function attemptsLabel(attempts: number, isCorrect: boolean): string {
  if (!isCorrect) return "Wrong";
  if (attempts === 1) return "1st try";
  if (attempts === 2) return "2nd try";
  if (attempts === 3) return "3rd try";
  return "4th try";
}

const LANG_COLORS: Record<string, { bg: string; border: string; text: string; dot: string }> = {
  English: { bg: "var(--surface-soft)", border: "var(--border)", text: "var(--text-muted)", dot: "var(--primary)" },
  Tamil: { bg: "var(--surface-soft)", border: "var(--border)", text: "var(--text-muted)", dot: "var(--primary)" },
  Sinhala: { bg: "var(--surface-soft)", border: "var(--border)", text: "var(--text-muted)", dot: "var(--primary)" },
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
        <circle cx="74" cy="74" r={radius} fill="none" stroke="rgba(0,0,0,0.07)" strokeWidth="12" />
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
    marks === 100 ? "var(--success)"
    : marks >= 50 ? "var(--warning)"
    : marks === 25 ? "var(--primary)"
    : "var(--danger)";
  return (
    <span
      className="inline-flex items-center justify-center w-12 h-8 rounded-lg text-xs font-black"
      style={{ background: "var(--surface-soft)", color, border: "1px solid var(--border)" }}
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
        <p className="text-xs text-stone-400 mt-0.5">{resource.source}</p>
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
function WeakTopicCard({
  rec,
  expanded,
  onToggle,
}: {
  rec: WeakTopicRecommendation;
  expanded: boolean;
  onToggle: () => void;
}) {
  const isEnrichment = rec.recommendation_type === "enrichment";
  return (
    <div
      className="rounded-2xl border overflow-hidden"
      style={{ background: "rgba(239,68,68,0.05)", borderColor: "rgba(239,68,68,0.18)" }}
    >
      {/* Header */}
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-6 py-4 text-left transition-colors duration-150 hover:bg-orange-900/5"
      >
        <div className="flex items-center gap-3">
          <span className="text-red-600/70">
            <BookOpenIcon className="w-5 h-5" />
          </span>
          <div>
            <p className="text-stone-900 font-bold text-base">{rec.topic}</p>
            <p className={isEnrichment ? "text-orange-600 text-xs font-semibold mt-0.5" : "text-red-600 text-xs font-semibold mt-0.5"}>
              {isEnrichment
                ? `${rec.percentage}% correct. Extra knowledge for continued mastery`
                : `${rec.percentage}% correct. Weak area - review recommended`}
            </p>
          </div>
        </div>
        <span
          className="text-stone-500 transition-transform duration-200"
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
                  style={{ background: "rgba(224,108,79,0.2)", color: "#f4a28c" }}
                >
                  <NoteIcon className="w-3 h-3" />
                </div>
                <p className="text-xs font-bold uppercase tracking-widest text-stone-500">Concept Notes</p>
              </div>
              <div
                className="rounded-xl p-4 space-y-2.5"
                style={{ background: "rgba(224,108,79,0.07)", border: "1px solid rgba(224,108,79,0.15)" }}
              >
                {rec.concept_notes.map((note, i) => {
                  // Bold the part before the first colon if it starts with **...**
                  const formatted = note.replace(/\*\*(.+?)\*\*/g, '<strong class="text-orange-700">$1</strong>');
                  return (
                    <div key={i} className="flex gap-2.5 text-sm leading-relaxed text-stone-900/75">
                      <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-violet-400" aria-hidden="true" />
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
                <p className="text-xs font-bold uppercase tracking-widest text-stone-500">Learning Resources</p>
              </div>
              <div className="space-y-2">
                {rec.resources.map((r, i) => (
                  <ResourceCard key={i} resource={r} />
                ))}
              </div>
            </div>
          )}
          {(!rec.resources || rec.resources.length === 0) && (
            <p className="rounded-xl border border-orange-900/10 bg-orange-900/[0.03] p-4 text-sm text-stone-500">
              No exact verified external link was found. The source-grounded notes above remain available for revision.
            </p>
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
    <tr className="border-t border-orange-900/10 hover:bg-orange-900/[0.03] transition-colors">
      <td className="py-3 px-4 text-stone-500 text-sm font-mono">Q{qm.q_num}</td>
      <td className="py-3 px-4 text-stone-900/70 text-sm max-w-[180px] truncate">{qm.topic}</td>
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
        <span className="text-stone-500 text-xs">{qm.hints_used}</span>
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
        <span className="text-sm text-stone-900/70 truncate max-w-[60%]">{topic}</span>
        <span className="text-sm font-bold" style={{ color }}>{correct}/{total} ({pct}%)</span>
      </div>
      <div className="h-2 rounded-full bg-orange-900/10 overflow-hidden">
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
        <div className="w-20 h-20 rounded-full border-4 border-orange-600/30 border-t-violet-500 animate-spin mx-auto mb-4" />
        <p className="text-stone-500">Generating your performance report...</p>
        <p className="text-stone-400 text-sm mt-1">Analysing weak areas &amp; preparing study notes</p>
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
      style={{ background: "rgba(0,0,0,0.03)", border: "1px solid rgba(0,0,0,0.08)" }}
    >
      <span className="text-xs font-bold uppercase tracking-widest text-stone-400 mr-2">Marks Scheme</span>
      {items.map((item) => (
        <div key={item.marks} className="flex items-center gap-1.5">
          <MarksBadge marks={item.marks} />
          <span className="text-xs text-stone-500">{item.label}</span>
        </div>
      ))}
    </div>
  );
}

// ── Rating Modal — WhatsApp-call-end style ────────────────────────
const RATING_LABELS: Record<number, string> = {
  1: "Not helpful",
  2: "Could be better",
  3: "Pretty good",
  4: "Really helpful",
  5: "Excellent",
};

function RatingModal({
  sessionId,
  onDismiss,
}: {
  sessionId: string;
  onDismiss: () => void;
}) {
  const [hovered, setHovered] = useState(0);
  const [selected, setSelected] = useState(0);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = useCallback(async () => {
    if (!selected) return;
    setSubmitting(true);
    try {
      await submitFeedback(sessionId, selected, comment.trim() || undefined);
    } catch {
      // Silent fail — feedback is optional, don't disrupt the UX
    } finally {
      setSubmitting(false);
      setSubmitted(true);
      // Auto-dismiss after showing thank-you
      setTimeout(onDismiss, 1800);
    }
  }, [sessionId, selected, comment, onDismiss]);

  const displayRating = hovered || selected;

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-end justify-center sm:items-center px-4 pb-6 sm:pb-0"
      style={{ background: "rgba(255,255,255,0.65)", backdropFilter: "blur(6px)" }}
      onClick={(e) => { if (e.target === e.currentTarget) onDismiss(); }}
    >
      {/* Modal card — slides up from bottom */}
      <div
        className="w-full max-w-sm rounded-3xl border p-7 animate-[slideUp_0.35s_cubic-bezier(0.34,1.56,0.64,1)]"
        style={{
          background: "linear-gradient(145deg, rgba(255,255,255,0.97), rgba(250,248,245,0.99))",
          borderColor: "rgba(224,108,79,0.25)",
          boxShadow: "0 -4px 60px rgba(224,108,79,0.2), 0 0 0 1px rgba(0,0,0,0.04) inset",
        }}
      >
        {submitted ? (
          /* ── Thank-you state ─── */
          <div className="text-center py-4 animate-[fadeIn_0.4s_ease-out]">
            <div
              className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4"
              style={{ background: "linear-gradient(135deg, rgba(52,211,153,0.25), rgba(16,185,129,0.15))", border: "1px solid rgba(52,211,153,0.3)" }}
            >
              <CheckIcon className="w-8 h-8 text-emerald-600" />
            </div>
            <p className="text-stone-900 font-bold text-lg">Thank you</p>
            <p className="text-stone-500 text-sm mt-1">Your feedback helps improve AdaptiveIQ</p>
          </div>
        ) : (
          <>
            {/* ── Header ─── */}
            <div className="flex items-start justify-between mb-5">
              <div>
                <p className="text-stone-900 font-bold text-lg leading-tight">How was your quiz?</p>
                <p className="text-stone-500 text-xs mt-0.5">Quick rating helps us improve</p>
              </div>
              <button
                id="btn-rating-skip"
                onClick={onDismiss}
                className="text-stone-400 hover:text-stone-900/60 transition-colors p-1 rounded-lg hover:bg-orange-900/5"
                aria-label="Skip rating"
              >
                <XIcon className="w-4 h-4" />
              </button>
            </div>

            {/* ── Star rating ─── */}
            <div className="flex justify-center gap-3 mb-3">
              {[1, 2, 3, 4, 5].map((n) => {
                const filled = n <= displayRating;
                return (
                  <button
                    key={n}
                    id={`star-${n}`}
                    onMouseEnter={() => setHovered(n)}
                    onMouseLeave={() => setHovered(0)}
                    onClick={() => setSelected(n)}
                    className="transition-all duration-150"
                    style={{
                      transform: filled ? "scale(1.25)" : "scale(1)",
                      filter: filled ? `drop-shadow(0 0 8px ${n <= selected ? "#fbbf24" : "#f4a28c"})` : "none",
                      color: filled
                        ? n <= selected
                          ? "#fbbf24"
                          : "#f4a28c"
                        : "rgba(0,0,0,0.15)",
                    }}
                    aria-label={`Rate ${n} star${n !== 1 ? "s" : ""}`}
                  >
                    {filled
                      ? <StarFillIcon className="w-9 h-9" />
                      : <StarIcon className="w-9 h-9" />}
                  </button>
                );
              })}
            </div>

            {/* ── Rating label ─── */}
            <p
              className="text-center text-sm font-semibold mb-5 h-5 transition-all duration-200"
              style={{ color: displayRating >= 4 ? "#34d399" : displayRating >= 3 ? "#fbbf24" : displayRating >= 1 ? "#f87171" : "transparent" }}
            >
              {displayRating ? RATING_LABELS[displayRating] : ""}
            </p>

            {/* ── Comment box ─── */}
            <textarea
              id="rating-comment"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Any comments? (optional)"
              maxLength={500}
              rows={2}
              className="w-full rounded-xl px-4 py-3 text-stone-900/80 placeholder-stone-400 text-sm border bg-white/50 outline-none resize-none transition-all duration-200 mb-4"
              style={{
                borderColor: comment ? "rgba(224,108,79,0.4)" : "rgba(0,0,0,0.1)",
                boxShadow: comment ? "0 0 0 1px rgba(224,108,79,0.2)" : "none",
              }}
            />

            {/* ── Actions ─── */}
            <div className="flex gap-3">
              <button
                id="btn-rating-submit"
                disabled={!selected || submitting}
                onClick={handleSubmit}
                className={`flex-1 py-3 rounded-xl font-bold text-sm transition-all duration-200 ${selected && !submitting ? "text-white" : "text-stone-400"}`}
                style={{
                  background: selected && !submitting
                    ? "linear-gradient(135deg, #e06c4f, #cc5234)"
                    : "rgba(0,0,0,0.05)",
                  boxShadow: selected && !submitting ? "0 4px 16px rgba(224,108,79,0.35)" : "none",
                  cursor: !selected || submitting ? "not-allowed" : "pointer",
                  opacity: !selected ? 0.5 : 1,
                }}
              >
                {submitting ? "Submitting..." : "Submit Feedback"}
              </button>
              <button
                id="btn-rating-skip-text"
                onClick={onDismiss}
                className="px-4 py-3 rounded-xl text-sm text-stone-400 hover:text-stone-900/60 transition-colors border border-orange-900/10 hover:border-orange-900/15 hover:bg-orange-900/5"
              >
                Skip
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ── Main Results Page ─────────────────────────────────────────────
export default function ResultsPage() {
  const params = useParams();
  const sessionId = params.sessionId as string;
  const [report, setReport] = useState<AnalyticsReport | null>(null);
  const [error, setError] = useState("");
  // Rating modal state
  const [showRating, setShowRating] = useState(false);
  // Accordion — only one weak-topic card open at a time
  const [openTopicIndex, setOpenTopicIndex] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    // Deep study notes + scraped resource links can take a while to generate
    // in the background (LLM call + live web lookups per weak topic). Keep
    // polling for a long time rather than silently giving up while the
    // "preparing" banner is still shown — a fetch/network error is a
    // different, much rarer case and keeps its own short retry budget.
    const MAX_PENDING_POLLS = 800; // ~20 min at 1.5s between polls
    const MAX_FETCH_RETRIES = 60;  // ~1 min of retries on network/server errors
    const load = async (fetchAttempt = 0, pendingPolls = 0) => {
      try {
        const nextReport = await getAnalyticsReport(sessionId);
        if (cancelled) return;
        setReport(nextReport);
        setError("");
        if (nextReport.recommendations_pending) {
          if (pendingPolls < MAX_PENDING_POLLS) {
            timer = setTimeout(() => load(0, pendingPolls + 1), 1500);
          }
          // else: exceeded the generous ceiling — stop polling, but never
          // pretend the notes are ready when they are not.
        } else {
          timer = setTimeout(() => setShowRating(true), 600);
        }
      } catch (e) {
        if (cancelled) return;
        if (fetchAttempt < MAX_FETCH_RETRIES) {
          timer = setTimeout(() => load(fetchAttempt + 1, pendingPolls), 1000);
        } else {
          setError(e instanceof Error ? e.message : "Could not load results");
        }
      }
    };
    load();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [sessionId]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="text-center">
          <div className="flex justify-center mb-4">
            <AlertTriangleIcon className="w-16 h-16 text-amber-600" />
          </div>
          <h1 className="text-2xl font-bold text-stone-900 mb-2">Could not load results</h1>
          <p className="text-stone-500 mb-6">{error}</p>
          <Link href="/" className="inline-block px-6 py-3 rounded-xl font-bold text-white"
            style={{ background: "linear-gradient(135deg, #e06c4f, #cc5234)" }}>
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
  const studyRecs = report.recommendations ?? [];

  const stats = [
    { icon: <CheckIcon className="w-5 h-5" />,      label: "Correct",      val: `${correctCount} / ${report.total_questions}`, color: "#34d399" },
    { icon: <TargetIcon className="w-5 h-5" />,     label: "Grade",        val: grade,                                          color: gradeColor },
    { icon: <LightbulbIcon className="w-5 h-5" />,  label: "Hints Used",   val: String(
        (report.question_marks_detail ?? []).reduce((s, q) => s + q.hints_used, 0)
      ),                                                                                          color: "#f4a28c" },
  ];

  return (
    <>
      {/* Rating modal — auto-appears after report loads */}
      {showRating && (
        <RatingModal sessionId={sessionId} onDismiss={() => setShowRating(false)} />
      )}

      <main className="min-h-screen py-10 px-4">
        {/* Nav */}
        <nav className="flex items-center justify-between max-w-5xl mx-auto mb-10">
          <Link href="/" className="flex items-center gap-2">
            <div className="brand-mark w-7 h-7 rounded-lg">
              <span className="font-bold text-xs">AQ</span>
            </div>
            <span className="font-bold text-base text-stone-900">AdaptiveIQ</span>
          </Link>
          <Link href="/upload" id="btn-new-quiz"
            className="flex items-center gap-2 text-sm text-orange-600 hover:text-orange-700 transition-colors font-semibold">
            New Quiz <ArrowRightIcon />
          </Link>
        </nav>

        <div className="max-w-5xl mx-auto animate-[fadeIn_0.5s_ease-out]">

          {/* ── Page Title ── */}
          <h1 className="text-4xl font-semibold text-stone-900 mb-1 tracking-tight">Quiz Complete</h1>
          <p className="text-stone-500 text-base mb-8">
            Here&apos;s your full performance breakdown, including marks, weak concepts, and study resources.
          </p>

          {report.recommendations_pending && (
            <div className="glass-card p-4 mb-6 text-sm text-stone-500 flex items-center gap-3" role="status">
              <span className="h-4 w-4 rounded-full border-2 border-orange-600/25 border-t-orange-600 animate-spin" />
              Your marks are ready. Deep study notes and exact resource links are being prepared.
            </div>
          )}
          {/* ── Score + Stats Row ── */}
          <div className="grid md:grid-cols-3 gap-5 mb-6">
            {/* Score ring */}
            <div
              className="rounded-2xl p-6 border flex flex-col items-center justify-center gap-3"
              style={{ background: "rgba(0,0,0,0.04)", borderColor: "rgba(0,0,0,0.1)", backdropFilter: "blur(12px)" }}
            >
              <ScoreRing score={finalPct} />
              <div className="text-center">
                <p className="text-stone-900 font-bold text-lg">
                  {marksEarned} / {marksPossible} marks
                </p>
                <p className="text-stone-500 text-xs mt-0.5">Attempt-weighted score</p>
              </div>
            </div>

            {/* Quick stats row */}
            <div className="md:col-span-2 grid grid-cols-1 sm:grid-cols-3 gap-4">
              {stats.map((s) => (
                <div
                  key={s.label}
                  className="rounded-xl p-5 border"
                  style={{ background: "rgba(0,0,0,0.04)", borderColor: "rgba(0,0,0,0.1)", backdropFilter: "blur(12px)" }}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span style={{ color: s.color }}>{s.icon}</span>
                    <span className="text-xs text-stone-500 font-semibold uppercase tracking-wide">{s.label}</span>
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
              style={{ background: "rgba(0,0,0,0.03)", borderColor: "rgba(0,0,0,0.09)", backdropFilter: "blur(12px)" }}
            >
              <div className="px-6 pt-5 pb-3 flex items-center gap-2">
                <span className="text-stone-900/60">
                  <ClipboardIcon className="w-5 h-5" />
                </span>
                <h2 className="font-bold text-stone-900 text-lg">Marks Breakdown</h2>
                <span className="ml-auto text-xs text-stone-400">Out of 100 per question</span>
              </div>
              <MarksLegend />
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead>
                    <tr className="border-t border-orange-900/15">
                      {["Q", "Topic", "Difficulty", "Result", "Hints", "Marks"].map((h) => (
                        <th key={h} className="py-2.5 px-4 text-xs font-bold uppercase tracking-widest text-stone-400">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {report.question_marks_detail.map((qm) => (
                      <QMarkRow key={qm.q_num} qm={qm} />
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="border-t border-orange-900/15 bg-orange-900/[0.03]">
                      <td colSpan={5} className="py-3 px-4 text-sm font-bold text-stone-900/60 text-right">Total Marks</td>
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
          {studyRecs.length > 0 && (
            <div className="mb-6">
              <div className="flex items-center gap-2 mb-4">
                <span className="text-orange-600">
                  <ZapIcon className="w-6 h-6" />
                </span>
                <h2 className="font-bold text-stone-900 text-xl">Weak Areas and Study Notes</h2>
              </div>
              <p className="text-stone-500 text-sm mb-5">
                Each weak area has its own card. Click a topic for deep notes, explanations, and exact learning resources. High scorers receive an extra-knowledge card instead.
              </p>
              <div className="space-y-3">
                {studyRecs.map((rec, i) => (
                  <WeakTopicCard
                    key={i}
                    rec={rec}
                    expanded={openTopicIndex === i}
                    onToggle={() => setOpenTopicIndex((v) => (v === i ? null : i))}
                  />
                ))}
              </div>
            </div>
          )}


          {/* ── Topic Performance Bars ── */}
          {topicEntries.length > 0 && (
            <div
              className="rounded-2xl p-6 border mb-5"
              style={{ background: "rgba(0,0,0,0.04)", borderColor: "rgba(0,0,0,0.09)", backdropFilter: "blur(12px)" }}
            >
              <h2 className="font-bold text-stone-900 text-lg mb-5 flex items-center gap-2">
                <span className="text-stone-900/60"><BarChartIcon className="w-5 h-5" /></span>
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
              className="flex flex-1 items-center justify-center gap-2 py-4 rounded-xl font-bold text-white text-center transition-all duration-200"
              style={{ background: "linear-gradient(135deg, #e06c4f, #cc5234)", boxShadow: "0 4px 20px rgba(224,108,79,0.35)" }}>
              Take Another Quiz <ArrowRightIcon />
            </Link>
            <button
              id="btn-export-results"
              onClick={() => {
                const html = `
<!DOCTYPE html>
<html>
<head>
<title>AdaptiveIQ Quiz Results</title>
<style>
  body { font-family: 'Inter', system-ui, sans-serif; background: #fcfaf6; color: #2d2926; padding: 40px; margin: 0; }
  .card { background: white; padding: 40px; border-radius: 16px; border: 1px solid #f1ebe0; max-width: 800px; margin: 0 auto; box-shadow: 0 10px 30px rgba(0,0,0,0.02); }
  h1 { color: #e06c4f; margin-top: 0; margin-bottom: 5px; font-size: 2rem; }
  .subtitle { color: #867253; font-size: 0.9rem; margin-bottom: 30px; }
  .stats { display: flex; gap: 15px; margin-bottom: 30px; }
  .stat { background: #f8f6f0; padding: 15px 20px; border-radius: 12px; flex: 1; text-align: center; border: 1px solid #f1ebe0; }
  .stat-val { font-size: 28px; font-weight: 800; color: #e06c4f; }
  .stat-lbl { font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #867253; font-weight: 700; margin-top: 5px; }
  table { width: 100%; border-collapse: collapse; text-align: left; margin-bottom: 30px; }
  th, td { padding: 14px 15px; border-bottom: 1px solid #f1ebe0; font-size: 14px; }
  th { font-size: 12px; text-transform: uppercase; color: #867253; background: #f8f6f0; font-weight: 700; }
  .correct { color: #059669; font-weight: 700; }
  .incorrect { color: #dc2626; font-weight: 700; }
  h3 { color: #3d3222; border-bottom: 2px solid #f1ebe0; padding-bottom: 10px; margin-top: 40px; }
  .notes { font-size: 14px; color: #3d3222; line-height: 1.6; }
  @page { size: A4; margin: 12mm; }
  @media print {
    body { background: white; padding: 0; }
    .card { max-width: none; box-shadow: none; border: 0; padding: 0; }
    tr, .stat { break-inside: avoid; }
  }
</style>
</head>
<body>
  <div class="card">
    <h1>AdaptiveIQ Results</h1>
    <div class="subtitle">Session: ${sessionId}</div>
    
    <div class="stats">
      <div class="stat">
        <div class="stat-val">${Math.round(report.final_score)}%</div>
        <div class="stat-lbl">Final Score</div>
      </div>
      <div class="stat">
        <div class="stat-val">${report.total_marks_earned} / ${report.total_marks_possible ?? (report.total_questions * 100)}</div>
        <div class="stat-lbl">Marks Earned</div>
      </div>
      <div class="stat">
        <div class="stat-val">${report.correct_count ?? Object.values(report.topic_scores || {}).reduce((s, v) => s + v.correct, 0)}</div>
        <div class="stat-lbl">Correct Answers</div>
      </div>
    </div>
    
    <h3>Question Breakdown</h3>
    <table>
      <thead>
        <tr><th>Q#</th><th>Topic</th><th>Result</th><th>Attempts</th><th>Marks</th></tr>
      </thead>
      <tbody>
            ${(report.question_marks_detail || []).map(q => `
        <tr>
          <td style="vertical-align: top;">${q.q_num}</td>
          <td style="vertical-align: top;">${q.topic}</td>
          <td style="vertical-align: top;" class="${q.is_correct ? 'correct' : 'incorrect'}">${q.is_correct ? 'Correct' : 'Incorrect'}</td>
          <td style="vertical-align: top;">${q.attempts}</td>
          <td style="vertical-align: top; font-weight:700">${q.marks}</td>
        </tr>
        <tr>
          <td colspan="5" style="padding: 15px; background: #fffdfa; border-bottom: 2px solid #f1ebe0;">
            <div style="font-weight: 600; margin-bottom: 8px; color: #3d3222;">Q: ${q.question}</div>
            <div style="margin-bottom: 12px; padding-left: 15px; font-size: 13px;">
              ${Object.entries(q.options || {}).map(([k, v]) => `
                <div style="margin-bottom: 4px; ${k === q.correct_answer ? 'color: #059669; font-weight: 700;' : ''} ${k === q.student_answer && k !== q.correct_answer ? 'color: #dc2626; text-decoration: line-through;' : ''}">
                  ${k}. ${v} ${k === q.student_answer ? '(Your Answer)' : ''} ${k === q.correct_answer ? '✓' : ''}
                </div>
              `).join('')}
            </div>
            <div style="font-size: 13px; color: #555; background: #f8f6f0; padding: 10px; border-left: 3px solid #e06c4f; border-radius: 4px; line-height: 1.5;">
              <strong>Explanation:</strong> ${q.model_answer || 'No explanation provided.'}
            </div>
            <div style="font-size: 12px; color: #705d50; margin-top: 10px;">
              <strong>Attempt history:</strong>
              ${(q.attempt_history || []).map(a => `Attempt ${a.attempt}: ${a.answer} (${a.is_correct ? 'correct' : 'incorrect'})`).join(' &nbsp;|&nbsp; ')}
            </div>
          </td>
        </tr>
        `).join('')}
      </tbody>
    </table>
    
    <h3>Study Recommendations</h3>
    <div class="notes">
      ${(report.recommendations || []).filter(r => r.concept_notes).map(r => `
        <div style="margin-bottom: 20px;">
          <strong>${r.topic} (${r.percentage}% correct)</strong>
          <ul style="margin-top: 8px;">
            ${(r.concept_notes || []).map(n => `<li>${n}</li>`).join('')}
          </ul>
        </div>
      `).join('') || '<p>No weak topics detected. Great job!</p>'}
    </div>
  </div>
</body>
</html>`;
                const printWindow = window.open("", "_blank", "noopener,noreferrer");
                if (printWindow) {
                  printWindow.document.write(html);
                  printWindow.document.close();
                  printWindow.focus();
                  window.setTimeout(() => printWindow.print(), 300);
                  return;
                }
                // Popup blockers should never make the recall sheet unusable.
                // Preserve the original HTML download as a safe fallback.
                const blob = new Blob([html], { type: "text/html" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `adaptiveiq-recall-sheet-${sessionId.slice(0, 8)}.html`;
                a.click();
                URL.revokeObjectURL(url);
              }}
              className="flex-1 py-4 rounded-xl font-bold border border-orange-900/15 bg-orange-900/5 text-stone-900/70 hover:text-stone-900 hover:bg-orange-900/10 transition-all duration-200 text-center"
            >
              Save Recall Sheet as PDF
            </button>
          </div>

          <p className="text-center text-stone-400 text-xs mt-6 font-mono">
            Session: {sessionId} | Grounding average: {Math.round((report.grounding_stats?.avg_grounding_score ?? 0) * 100)}%
          </p>
        </div>
      </main>
    </>
  );
}
