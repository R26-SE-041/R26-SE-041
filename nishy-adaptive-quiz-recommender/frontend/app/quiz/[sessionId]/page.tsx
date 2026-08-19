"use client";

import { useEffect, useState, useRef, useCallback, useMemo } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import { getSessionStatus, getCurrentQuestion, submitAnswer } from "@/lib/api";
import type {
  SessionStatusResponse,
  Question,
  SubmitAnswerResponse,
} from "@/types/quiz";
import {
  CheckIcon,
  XIcon,
  AlertTriangleIcon,
  CheckCircleIcon,
  XCircleIcon,
  LightbulbIcon,
  ClockIcon,
  ZapIcon,
  EyeIcon,
  LockIcon,
  TagIcon,
  RefreshIcon,
  ArrowLeftIcon,
} from "@/components/ui/Icons";

// ── Seeded deterministic shuffle ────────────────────────────────
function seededShuffle<T>(arr: T[], seed: string): T[] {
  const out = [...arr];
  let hash = 0;
  for (let i = 0; i < seed.length; i++) {
    hash = ((hash << 5) - hash + seed.charCodeAt(i)) | 0;
  }
  let s = Math.abs(hash);
  for (let i = out.length - 1; i > 0; i--) {
    s = (s * 1664525 + 1013904223) & 0xffffffff;
    const j = Math.abs(s) % (i + 1);
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

// ── Difficulty badge ─────────────────────────────────────────────
function DifficultyBadge({ score }: { score: number }) {
  const { label, color } =
    score < 0.33
      ? { label: "Easy", color: "#34d399" }
      : score < 0.66
        ? { label: "Medium", color: "#fbbf24" }
        : { label: "Hard", color: "#f87171" };
  return (
    <span
      className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border"
      style={{ color, borderColor: `${color}40`, background: `${color}15` }}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />
      {label}
    </span>
  );
}

function BloomBadge({ level }: { level: string }) {
  return (
    <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-violet-500/20 text-violet-300 border border-violet-500/30 capitalize">
      {level}
    </span>
  );
}

// ── Processing screen ────────────────────────────────────────────
function ProcessingScreen({ status }: { status: SessionStatusResponse | null }) {
  const isReady = status?.status === "ready";
  const isError = status?.status === "error";
  const steps = [
    { id: "upload",    label: "Files uploaded",                        done: true },
    { id: "ingest",    label: "Extracting text chunks",                done: isReady || (status?.chunk_count ?? 0) > 0 },
    { id: "knowledge", label: "Identifying topics",                    done: isReady || (status?.topics_detected?.length ?? 0) > 0 },
    { id: "quiz",      label: "Generating questions with Qwen2.5-7B", done: isReady },
  ];
  if (isError) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="max-w-md w-full text-center">
          <div className="mb-6 flex justify-center">
            <XCircleIcon className="w-16 h-16 text-red-400" />
          </div>
          <h1 className="text-2xl font-bold text-red-300 mb-3">Setup Failed</h1>
          <p className="text-white/50 text-sm mb-6">{status?.message}</p>
          <a href="/upload" className="inline-block px-6 py-3 rounded-xl font-bold text-white"
            style={{ background: "linear-gradient(135deg, #7c3aed, #4f46e5)" }}>← Try Again</a>
        </div>
      </div>
    );
  }
  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="max-w-md w-full text-center">
        <div className="relative w-24 h-24 mx-auto mb-8">
          <div className="absolute inset-0 rounded-full border-4 border-violet-500/20" />
          <div className={`absolute inset-0 rounded-full border-4 border-transparent border-t-violet-500 ${isReady ? "" : "animate-spin"}`} style={{ animationDuration: "1.2s" }} />
          <div className="absolute inset-3 rounded-full flex items-center justify-center">
            {isReady
              ? <CheckCircleIcon className="w-9 h-9 text-emerald-400" />
              : <ZapIcon className="w-9 h-9 text-violet-400" />}
          </div>
        </div>
        <h1 className="text-2xl font-bold text-white mb-2">{isReady ? "Almost ready!" : "Processing your documents"}</h1>
        <p className="text-white/50 text-sm mb-8">{status?.message ?? "Initializing agents..."}</p>
        <div className="space-y-3 text-left">
          {steps.map((step) => (
            <div key={step.id} className="flex items-center gap-3 px-4 py-3 rounded-xl border"
              style={{ background: step.done ? "rgba(52,211,153,0.08)" : "rgba(255,255,255,0.03)", borderColor: step.done ? "rgba(52,211,153,0.2)" : "rgba(255,255,255,0.08)" }}>
              <span>
                {step.done
                  ? <CheckIcon className="w-5 h-5 text-emerald-400" />
                  : <ClockIcon className="w-5 h-5 text-white/30" />}
              </span>
              <span className={`text-sm font-medium ${step.done ? "text-emerald-300" : "text-white/40"}`}>{step.label}</span>
              {!step.done && <span className="ml-auto text-xs text-white/30 animate-pulse">running...</span>}
            </div>
          ))}
        </div>
        {status?.topics_detected && status.topics_detected.length > 0 && (
          <div className="mt-6 text-left">
            <p className="text-xs font-semibold uppercase tracking-widest text-white/30 mb-2">Topics detected</p>
            <div className="flex flex-wrap gap-2">
              {status.topics_detected.slice(0, 6).map((t) => (
                <span key={t} className="px-2.5 py-1 rounded-full text-xs bg-violet-500/15 text-violet-300 border border-violet-500/25">{t}</span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Hint level badge — attempt 1=Hard, 2=Medium, 3=Easy ─────────
function HintLevelBadge({ attempts }: { attempts: number }) {
  const levels: Record<number, { label: string; color: string; desc: string }> = {
    1: { label: "Hard Hint",   color: "#ef4444", desc: "Conceptual nudge — think deeper" },
    2: { label: "Medium Hint", color: "#f59e0b", desc: "Focused concept explanation" },
    3: { label: "Easy Hint",   color: "#34d399", desc: "Step-by-step walkthrough" },
  };
  const info = levels[attempts] ?? levels[1];
  return (
    <div className="flex items-center gap-2 mb-3">
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold"
        style={{ background: `${info.color}20`, color: info.color, border: `1px solid ${info.color}40` }}>
        <LightbulbIcon className="w-3.5 h-3.5" /> {info.label}
      </span>
      <span className="text-xs text-white/40">{info.desc}</span>
    </div>
  );
}

// ── Answered record stored in history ───────────────────────────
interface AnsweredRecord {
  question: Question;
  shuffledKeys: string[];
  selectedDisplayKey: string;
  result: SubmitAnswerResponse;
}

// ── Feedback Card — NO Next button inside ───────────────────────
function FeedbackCard({
  result,
  onTryAgain,
  shuffledKeys,
  isRetrying,
}: {
  result: SubmitAnswerResponse;
  onTryAgain: () => void;
  shuffledKeys: string[];
  isRetrying: boolean;
}) {
  const canTryAgain = !result.is_correct && result.attempts < 4;
  const isFinalWrong = !result.is_correct && !canTryAgain;
  const hintText = result.hint;

  // Map original correct answer letter → display position label
  const correctDisplayKey = (() => {
    const m = result.feedback?.match(/\*\*([A-D])\*\*/);
    if (!m) return null;
    const origKey = m[1];
    const dispIdx = shuffledKeys.indexOf(origKey);
    return dispIdx >= 0 ? String.fromCharCode(65 + dispIdx) : origKey;
  })();

  const hintBg = result.attempts === 1
    ? { bg: "rgba(239,68,68,0.07)", border: "rgba(239,68,68,0.2)" }
    : result.attempts === 2
      ? { bg: "rgba(245,158,11,0.08)", border: "rgba(245,158,11,0.2)" }
      : { bg: "rgba(52,211,153,0.07)", border: "rgba(52,211,153,0.2)" };

  return (
    <div className="w-full mt-6 animate-[slideUp_0.3s_ease-out]">
      <div className="relative w-full rounded-2xl p-6 border"
        style={{
          background: result.is_correct
            ? "linear-gradient(135deg, rgba(16,185,129,0.15), rgba(5,150,105,0.1))"
            : canTryAgain
              ? "linear-gradient(135deg, rgba(245,158,11,0.12), rgba(217,119,6,0.08))"
              : "linear-gradient(135deg, rgba(239,68,68,0.12), rgba(220,38,38,0.08))",
          borderColor: result.is_correct
            ? "rgba(52,211,153,0.3)"
            : canTryAgain ? "rgba(251,191,36,0.3)" : "rgba(248,113,113,0.3)",
          backdropFilter: "blur(16px)",
        }}>

        {/* Header */}
        <div className="flex items-center gap-3 mb-4">
          <span>
            {result.is_correct
              ? <CheckCircleIcon className="w-10 h-10 text-emerald-400" />
              : canTryAgain
              ? <LightbulbIcon className="w-10 h-10 text-amber-400" />
              : <XCircleIcon className="w-10 h-10 text-red-400" />}
          </span>
          <div>
            <h3 className={`font-bold text-xl ${result.is_correct ? "text-emerald-300" : canTryAgain ? "text-amber-300" : "text-red-300"}`}>
              {result.is_correct ? "Correct!" : canTryAgain ? "Not quite — here's a hint" : "Incorrect"}
            </h3>
            <p className="text-white/50 text-sm">
              {result.is_correct
                ? `Score: ${Math.round(result.score * 100)}%`
                : canTryAgain
                  ? `Attempt ${result.attempts} of 4 — ${4 - result.attempts} attempt${4 - result.attempts !== 1 ? "s" : ""} left`
                  : "Answer revealed — move to next"}
            </p>
          </div>
        </div>

        {/* Hint — attempts 1, 2, 3 */}
        {!result.is_correct && canTryAgain && hintText && (
          <div className="mb-5">
            <HintLevelBadge attempts={result.attempts} />
            <div className="rounded-xl px-4 py-3 text-sm text-white/80 leading-relaxed"
              style={{ background: hintBg.bg, border: `1px solid ${hintBg.border}` }}>
              {hintText}
            </div>
          </div>
        )}

        {/* Final wrong */}
        {isFinalWrong && (
          <div className="mb-5">
            {correctDisplayKey && (
              <p className="text-red-300 font-bold text-sm mb-2 flex items-center gap-1.5">
                <XIcon className="w-3.5 h-3.5 shrink-0" />
                Correct answer: <span className="text-white bg-red-500/20 px-2 py-0.5 rounded font-mono">{correctDisplayKey}</span>
              </p>
            )}
            <p className="text-white/70 text-sm leading-relaxed">{result.feedback}</p>
          </div>
        )}

        {/* Correct — explanation only */}
        {result.is_correct && (
          <p className="text-white/70 text-sm leading-relaxed">{result.feedback}</p>
        )}

        {/* Try Again — only for hints, no Next here */}
        {canTryAgain && !isRetrying && (
          <div className="mt-5">
            <button id="btn-try-again" onClick={onTryAgain}
              className="w-full py-3 rounded-xl font-bold text-white transition-all duration-200"
              style={{ background: "linear-gradient(135deg, #f59e0b, #d97706)", boxShadow: "0 4px 20px rgba(245,158,11,0.3)" }}>
              <span className="flex items-center justify-center gap-2">
                Try Again <RefreshIcon className="w-4 h-4" />
              </span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Read-only view of answered question ─────────────────────────
function PreviousQuestionView({ record }: { record: AnsweredRecord }) {
  const { question, shuffledKeys, result } = record;
  const opts = question.options;
  return (
    <div className="opacity-90">
      <div className="flex items-center gap-3 mb-6 flex-wrap">
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-white/5 text-white/50 border border-white/10">
          <TagIcon className="w-3 h-3" /> {question.topic}
        </span>
        <BloomBadge level={question.bloom_level} />
        <DifficultyBadge score={question.difficulty} />
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-violet-500/10 text-violet-400/60 border border-violet-500/20">
          <LockIcon className="w-3 h-3" /> Reviewed
        </span>
      </div>
      <p className="text-white text-xl font-semibold leading-relaxed mb-8">{question.question}</p>
      {opts && (
        <div className="space-y-3">
          {shuffledKeys.map((origKey, idx) => {
            const displayKey = String.fromCharCode(65 + idx);
            const optText = opts[origKey as keyof typeof opts];
            const userPicked = record.selectedDisplayKey === displayKey;
            const isAnswerKey = result.is_correct ? userPicked : !!result.feedback?.includes(`**${origKey}**`);
            let bg = "rgba(255,255,255,0.03)";
            let border = "rgba(255,255,255,0.08)";
            let labelBg = "rgba(255,255,255,0.06)";
            let labelColor = "rgba(255,255,255,0.5)";
            if (isAnswerKey) { bg = "rgba(52,211,153,0.1)"; border = "rgba(52,211,153,0.3)"; labelBg = "rgba(52,211,153,0.2)"; labelColor = "#34d399"; }
            else if (userPicked) { bg = "rgba(239,68,68,0.1)"; border = "rgba(239,68,68,0.3)"; labelBg = "rgba(239,68,68,0.2)"; labelColor = "#f87171"; }
            return (
              <div key={origKey} className="flex items-center gap-4 px-5 py-4 rounded-xl border" style={{ background: bg, borderColor: border }}>
                <span className="w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold shrink-0" style={{ background: labelBg, color: labelColor }}>{displayKey}</span>
                <span className="text-sm font-medium text-white/70">{optText}</span>
                {isAnswerKey && (
                  <span className="ml-auto text-emerald-400 text-xs font-bold flex items-center gap-1">
                    <CheckIcon className="w-3 h-3" /> Correct
                  </span>
                )}
                {userPicked && !isAnswerKey && (
                  <span className="ml-auto text-red-400 text-xs font-bold flex items-center gap-1">
                    <XIcon className="w-3 h-3" /> Your answer
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}
      <div className="mt-4 px-4 py-3 rounded-xl border"
        style={{ background: result.is_correct ? "rgba(52,211,153,0.07)" : "rgba(239,68,68,0.07)", borderColor: result.is_correct ? "rgba(52,211,153,0.2)" : "rgba(239,68,68,0.2)" }}>
        <p className="text-white/60 text-sm leading-relaxed">{result.feedback}</p>
      </div>
    </div>
  );
}

// ── Nav button helper ────────────────────────────────────────────
function NavBtn({ id, disabled, onClick, children, className = "" }: { id: string; disabled: boolean; onClick: () => void; children: React.ReactNode; className?: string }) {
  return (
    <button id={id} disabled={disabled} onClick={onClick}
      className={`px-5 py-4 rounded-xl font-semibold text-sm transition-all duration-200 flex items-center gap-2 border ${className}`}
      style={{
        background: disabled ? "rgba(255,255,255,0.02)" : "rgba(255,255,255,0.06)",
        borderColor: disabled ? "rgba(255,255,255,0.04)" : "rgba(255,255,255,0.12)",
        color: disabled ? "rgba(255,255,255,0.15)" : "rgba(255,255,255,0.7)",
        cursor: disabled ? "not-allowed" : "pointer",
      }}>
      {children}
    </button>
  );
}

// ── Main quiz page ──────────────────────────────────────────────
export default function QuizPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string;

  const [sessionStatus, setSessionStatus] = useState<SessionStatusResponse | null>(null);
  const [question, setQuestion] = useState<Question | null>(null);
  const [selectedDisplayKey, setSelectedDisplayKey] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<SubmitAnswerResponse | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);
  const [error, setError] = useState("");
  const [startTime, setStartTime] = useState(Date.now());
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Answered question history for prev navigation
  const [history, setHistory] = useState<AnsweredRecord[]>([]);
  // -1 = live current question; >=0 = reviewing history[viewIndex]
  const [viewIndex, setViewIndex] = useState<number>(-1);

  // Stable shuffled option keys for current question (seeded by q_id)
  const shuffledKeys = useMemo<string[]>(() => {
    if (!question?.options) return ["A", "B", "C", "D"];
    return seededShuffle(["A", "B", "C", "D"], question.q_id);
  }, [question?.q_id, question?.options]);

  // Poll for session readiness
  const pollStatus = useCallback(async () => {
    try {
      const status = await getSessionStatus(sessionId);
      setSessionStatus(status);
      if (status.status === "ready") {
        if (pollingRef.current) clearInterval(pollingRef.current);
        const q = await getCurrentQuestion(sessionId);
        setQuestion(q);
        setStartTime(Date.now());
      } else if (status.status === "error") {
        if (pollingRef.current) clearInterval(pollingRef.current);
      }
    } catch {
      setError("Could not connect to server. Is the backend running?");
    }
  }, [sessionId]);

  useEffect(() => {
    pollStatus();
    pollingRef.current = setInterval(pollStatus, 3000);
    return () => { if (pollingRef.current) clearInterval(pollingRef.current); };
  }, [pollStatus]);

  const handleSubmit = async () => {
    if (!selectedDisplayKey || !question) return;
    setSubmitting(true);
    const timeSec = Math.round((Date.now() - startTime) / 1000);
    // Map display position → original answer key for backend
    const dispIdx = selectedDisplayKey.charCodeAt(0) - 65;
    const originalKey = shuffledKeys[dispIdx] ?? selectedDisplayKey;
    try {
      setIsRetrying(false);
      const res = await submitAnswer(sessionId, { q_id: question.q_id, answer: originalKey, time_taken_sec: timeSec });
      setResult(res);
      // Save to history only when this attempt is terminal (correct or attempt 4)
      if (res.is_correct || res.attempts >= 4) {
        setHistory((prev) => [...prev, { question, shuffledKeys, selectedDisplayKey, result: res }]);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Submission failed");
    } finally {
      setSubmitting(false);
    }
  };

  const handleTryAgain = () => {
    setIsRetrying(true);
    setSelectedDisplayKey(null);
    setError("");
    setStartTime(Date.now());
  };

  const handleNextQuestion = async () => {
    if (result?.quiz_complete) { router.push(`/quiz/${sessionId}/results`); return; }
    setResult(null);
    setIsRetrying(false);
    setSelectedDisplayKey(null);
    setError("");
    setViewIndex(-1);
    try {
      const q = await getCurrentQuestion(sessionId);
      setQuestion(q);
      setStartTime(Date.now());
    } catch { setError("Could not load next question."); }
  };

  // ── Render: still loading ────────────────────────────────────
  if (!question) return <ProcessingScreen status={sessionStatus} />;

  const isViewingHistory = viewIndex >= 0;
  const isLive = viewIndex === -1;
  const answerResolved = !!result && !isRetrying && (result.is_correct || result.attempts >= 4);

  const progress = ((question.q_index + 1) / question.total_questions) * 100;
  const displayedQNum = isViewingHistory ? history[viewIndex].question.q_index + 1 : question.q_index + 1;

  return (
    <main className="min-h-screen py-8 px-4">
      <div className="max-w-3xl mx-auto">

        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <Link href="/" className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: "linear-gradient(135deg, #7c3aed, #4f46e5)" }}>
              <span className="text-white font-bold text-xs">AQ</span>
            </div>
            <span className="font-bold text-base text-white">AdaptiveIQ</span>
          </Link>
          <span className="text-sm text-white/40">
            {isViewingHistory
              ? <span className="text-violet-300/60">Reviewing Q{displayedQNum}</span>
              : `Question ${question.q_index + 1} of ${question.total_questions}`}
          </span>
        </div>

        {/* Progress bar */}
        <div className="w-full h-1.5 rounded-full bg-white/10 mb-8 overflow-hidden">
          <div className="h-full rounded-full transition-all duration-500"
            style={{ width: `${progress}%`, background: "linear-gradient(90deg, #8b5cf6, #22d3ee)" }} />
        </div>

        {/* Review banner */}
        {isViewingHistory && (
          <div className="mb-4 px-4 py-2.5 rounded-xl border border-violet-500/20 bg-violet-500/5 flex items-center gap-2">
            <span className="text-violet-300 text-xs font-semibold flex items-center gap-1.5">
              <EyeIcon className="w-3.5 h-3.5" /> Reviewing Q{displayedQNum}
            </span>
            <span className="text-white/30 text-xs">— Read only</span>
          </div>
        )}

        {/* Question card */}
        <div className="rounded-2xl p-8 border mb-6 animate-[fadeIn_0.4s_ease-out]"
          style={{ background: "rgba(255,255,255,0.04)", borderColor: isViewingHistory ? "rgba(139,92,246,0.15)" : "rgba(255,255,255,0.1)", backdropFilter: "blur(12px)" }}>
          {isViewingHistory ? (
            <PreviousQuestionView record={history[viewIndex]} />
          ) : (
            <>
              {/* Meta */}
              <div className="flex items-center gap-3 mb-6 flex-wrap">
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-white/5 text-white/50 border border-white/10">
                  <TagIcon className="w-3 h-3" /> {question.topic}
                </span>
                <BloomBadge level={question.bloom_level} />
                <DifficultyBadge score={question.difficulty} />
                {question.is_flagged && (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/25">
                    <AlertTriangleIcon className="w-3 h-3" /> Low grounding
                  </span>
                )}
              </div>
              <p className="text-white text-xl font-semibold leading-relaxed mb-8">{question.question}</p>

              {/* MCQ options — shuffled display */}
              {question.q_type === "mcq" && question.options && (
                <div className="space-y-3">
                  {shuffledKeys.map((origKey, idx) => {
                    const displayKey = String.fromCharCode(65 + idx);
                    const opt = question.options![origKey as keyof typeof question.options];
                    const selected = selectedDisplayKey === displayKey;
                    return (
                      <button key={origKey} id={`option-${displayKey}`}
                        onClick={() => (!result || isRetrying) && setSelectedDisplayKey(displayKey)}
                        disabled={!!result && !isRetrying}
                        className="w-full text-left flex items-center gap-4 px-5 py-4 rounded-xl border transition-all duration-200"
                        style={{
                          background: selected ? "rgba(139,92,246,0.2)" : "rgba(255,255,255,0.03)",
                          borderColor: selected ? "rgba(139,92,246,0.6)" : "rgba(255,255,255,0.08)",
                          transform: selected ? "scale(1.01)" : "scale(1)",
                          cursor: (result && !isRetrying) ? "default" : "pointer",
                        }}>
                        <span className="w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold shrink-0"
                          style={{ background: selected ? "rgba(139,92,246,0.4)" : "rgba(255,255,255,0.06)", color: selected ? "#c4b5fd" : "rgba(255,255,255,0.5)" }}>
                          {displayKey}
                        </span>
                        <span className={`text-sm font-medium ${selected ? "text-white" : "text-white/70"}`}>{opt}</span>
                      </button>
                    );
                  })}
                </div>
              )}

              {/* Essay / structured */}
              {question.q_type !== "mcq" && (
                <textarea id="essay-answer" placeholder="Type your answer here..."
                  className="w-full min-h-[160px] rounded-xl px-4 py-3 text-white placeholder-white/30 border border-white/10 bg-white/5 backdrop-blur-sm outline-none focus:border-violet-500/60 text-sm leading-relaxed resize-none transition-all duration-200"
                  onChange={(e) => setSelectedDisplayKey(e.target.value)} disabled={!!result && !isRetrying} />
              )}
            </>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 rounded-xl px-4 py-3 border border-red-500/30 bg-red-500/10 text-red-300 text-sm flex items-center gap-2">
            <AlertTriangleIcon className="w-4 h-4 shrink-0" /> {error}
          </div>
        )}

        {/* ── Nav bar — always visible ──────────────────────────── */}
        {isViewingHistory ? (
          /* History nav */
          <div className="flex items-center gap-3 mb-4">
            <NavBtn id="btn-hist-prev" disabled={viewIndex <= 0} onClick={() => setViewIndex((v) => v - 1)}>← Prev</NavBtn>
            <button id="btn-hist-return" onClick={() => setViewIndex(-1)}
              className="flex-1 py-4 rounded-xl font-semibold text-white/80 text-sm transition-all duration-200 border flex items-center justify-center gap-2"
              style={{ background: "rgba(139,92,246,0.12)", borderColor: "rgba(139,92,246,0.3)" }}>
              <ArrowLeftIcon className="w-4 h-4" /> Back to Current Question
            </button>
            <NavBtn id="btn-hist-next" disabled={false} onClick={() => setViewIndex((v) => v >= history.length - 1 ? -1 : v + 1)}>Next →</NavBtn>
          </div>
        ) : !answerResolved ? (
          /* Submit bar */
          <div className="flex items-center gap-3 mb-4">
            <NavBtn id="btn-prev-question" disabled={history.length === 0} onClick={() => setViewIndex(history.length - 1)}>← Prev</NavBtn>
            <button id="btn-submit-answer" onClick={handleSubmit} disabled={!selectedDisplayKey || submitting}
              className="flex-1 py-4 rounded-xl font-bold text-white text-base transition-all duration-200"
              style={{
                background: !selectedDisplayKey || submitting ? "rgba(255,255,255,0.06)" : "linear-gradient(135deg, #7c3aed, #4f46e5)",
                boxShadow: selectedDisplayKey && !submitting ? "0 4px 20px rgba(124,58,237,0.4)" : "none",
                cursor: !selectedDisplayKey || submitting ? "not-allowed" : "pointer",
              }}>
              {submitting ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Evaluating...
                </span>
              ) : "Submit Answer →"}
            </button>
            <NavBtn id="btn-next-disabled" disabled={true} onClick={() => {}}>Next →</NavBtn>
          </div>
        ) : (
          /* After answer resolved */
          <div className="flex items-center gap-3 mb-4">
            <NavBtn id="btn-prev-after" disabled={history.length === 0} onClick={() => setViewIndex(history.length - 1)}>← Prev</NavBtn>
            <button id="btn-next-question" onClick={handleNextQuestion}
              className="flex-1 py-4 rounded-xl font-bold text-white text-base transition-all duration-200"
              style={{
                background: result?.quiz_complete ? "linear-gradient(135deg, #059669, #0891b2)" : "linear-gradient(135deg, #7c3aed, #4f46e5)",
                boxShadow: `0 4px 20px ${result?.quiz_complete ? "rgba(5,150,105,0.3)" : "rgba(124,58,237,0.4)"}`,
              }}>
              {result?.quiz_complete ? "View Results →" : "Next Question →"}
            </button>
          </div>
        )}

        {/* Adaptive difficulty dots */}
        {isLive && (
          <div className="mt-2 flex items-center justify-center gap-2">
            <span className="text-xs text-white/25">Adaptive difficulty</span>
            <div className="flex gap-1">
              {[1, 2, 3].map((n) => (
                <div key={n} className="w-1.5 h-1.5 rounded-full" style={{
                  background:
                    question.difficulty < 0.33 && n === 1 ? "#34d399"
                      : question.difficulty >= 0.33 && question.difficulty < 0.66 && n <= 2 ? "#fbbf24"
                        : question.difficulty >= 0.66 && n <= 3 ? "#f87171"
                          : "rgba(255,255,255,0.1)",
                }} />
              ))}
            </div>
          </div>
        )}

        {/* Feedback card — only on live question */}
        {isLive && result && (
          <FeedbackCard result={result} onTryAgain={handleTryAgain} shuffledKeys={shuffledKeys} isRetrying={isRetrying} />
        )}
      </div>
    </main>
  );
}
