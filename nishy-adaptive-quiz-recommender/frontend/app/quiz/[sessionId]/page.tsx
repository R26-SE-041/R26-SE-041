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
  ArrowRightIcon,
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
      ? { label: "Easy", color: "var(--success)" }
      : score < 0.66
        ? { label: "Medium", color: "var(--warning)" }
        : { label: "Hard", color: "var(--danger)" };
  return (
    <span
      className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border"
      style={{ color, borderColor: "var(--border)", background: "var(--surface-soft)" }}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />
      {label}
    </span>
  );
}

function BloomBadge({ level }: { level: string }) {
  return (
    <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-orange-600/20 text-orange-700 border border-orange-600/30 capitalize">
      {level}
    </span>
  );
}

// ── Processing screen ────────────────────────────────────────────
function ProcessingScreen({ status }: { status: SessionStatusResponse | null }) {
  const isReady = status?.status === "ready";
  const isError = status?.status === "error";
  const isTopicSession = status?.is_topic_session === true;
  const steps = isTopicSession ? [
    { id: "quiz", label: `Generating questions on "${status?.topics_detected?.[0] || 'Topic'}"...`, done: isReady }
  ] : [
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
            <XCircleIcon className="w-16 h-16 text-red-600" />
          </div>
          <h1 className="text-2xl font-bold text-red-700 mb-3">Setup Failed</h1>
          <p className="text-stone-500 text-sm mb-6">{status?.message}</p>
          <a href="/upload" className="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-bold text-white"
            style={{ background: "linear-gradient(135deg, #e06c4f, #cc5234)" }}><ArrowLeftIcon /> Try Again</a>
        </div>
      </div>
    );
  }
  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="max-w-md w-full text-center">
        <div className="relative w-24 h-24 mx-auto mb-8">
          <div className="absolute inset-0 rounded-full border-4 border-orange-600/20" />
          <div className={`absolute inset-0 rounded-full border-4 border-transparent border-t-violet-500 ${isReady ? "" : "animate-spin"}`} style={{ animationDuration: "1.2s" }} />
          <div className="absolute inset-3 rounded-full flex items-center justify-center">
            {isReady
              ? <CheckCircleIcon className="w-9 h-9 text-emerald-600" />
              : <ZapIcon className="w-9 h-9 text-orange-600" />}
          </div>
        </div>
        <h1 className="text-2xl font-bold text-stone-900 mb-2">{isReady ? "Almost ready!" : (isTopicSession ? "Generating your quiz" : "Processing your documents")}</h1>
        <p className="text-stone-500 text-sm mb-8">{status?.message ?? "Initializing agents..."}</p>
        <div className="space-y-3 text-left">
          {steps.map((step) => (
            <div key={step.id} className="flex items-center gap-3 px-4 py-3 rounded-xl border"
              style={{ background: step.done ? "rgba(52,211,153,0.08)" : "rgba(0,0,0,0.03)", borderColor: step.done ? "rgba(52,211,153,0.2)" : "rgba(0,0,0,0.08)" }}>
              <span>
                {step.done
                  ? <CheckIcon className="w-5 h-5 text-emerald-600" />
                  : <ClockIcon className="w-5 h-5 text-stone-400" />}
              </span>
              <span className={`text-sm font-medium ${step.done ? "text-emerald-700" : "text-stone-500"}`}>{step.label}</span>
              {!step.done && <span className="ml-auto text-xs text-stone-400 animate-pulse">running...</span>}
            </div>
          ))}
        </div>
        {status?.topics_detected && status.topics_detected.length > 0 && (
          <div className="mt-6 text-left">
            <p className="text-xs font-semibold uppercase tracking-widest text-stone-400 mb-2">Topics detected</p>
            <div className="flex flex-wrap gap-2">
              {status.topics_detected.slice(0, 6).map((t) => (
                <span key={t} className="px-2.5 py-1 rounded-full text-xs bg-orange-600/15 text-orange-700 border border-orange-600/25">{t}</span>
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
    1: { label: "Hard Hint",   color: "var(--danger)", desc: "A conceptual prompt to guide deeper reasoning" },
    2: { label: "Medium Hint", color: "var(--warning)", desc: "Focused concept explanation" },
    3: { label: "Easy Hint",   color: "var(--success)", desc: "Step-by-step walkthrough" },
  };
  const info = levels[attempts] ?? levels[1];
  return (
    <div className="flex items-center gap-2 mb-3">
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold"
        style={{ background: "var(--surface-soft)", color: info.color, border: "1px solid var(--border)" }}>
        <LightbulbIcon className="w-3.5 h-3.5" /> {info.label}
      </span>
      <span className="text-xs text-stone-500">{info.desc}</span>
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

  const legacyAnswerMatch = result.feedback?.match(/\*\*([1-5])(?:\s+-\s+(.+?))?\*\*/);
  const correctOriginalKey = result.correct_answer ?? legacyAnswerMatch?.[1] ?? null;
  const correctAnswerText = result.correct_answer_text ?? legacyAnswerMatch?.[2] ?? null;
  const finalExplanation = result.explanation ?? result.feedback
    ?.split("**Detailed Explanation:**")[1]
    ?.trim();

  // Map the original correct option number to its shuffled display number.
  const correctDisplayKey = (() => {
    if (!correctOriginalKey) return null;
    const dispIdx = shuffledKeys.indexOf(correctOriginalKey);
    return dispIdx >= 0 ? String(dispIdx + 1) : correctOriginalKey;
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
              ? <CheckCircleIcon className="w-10 h-10 text-emerald-600" />
              : canTryAgain
              ? <LightbulbIcon className="w-10 h-10 text-amber-600" />
              : <XCircleIcon className="w-10 h-10 text-red-600" />}
          </span>
          <div>
            <h3 className={`font-bold text-xl ${result.is_correct ? "text-emerald-700" : canTryAgain ? "text-amber-700" : "text-red-700"}`}>
              {result.is_correct ? "Correct" : canTryAgain ? "Not quite. Here is a hint" : "Incorrect"}
            </h3>
            <p className="text-stone-500 text-sm">
              {result.is_correct
                ? `Score: ${Math.round(result.score * 100)}%`
                : canTryAgain
                  ? `Attempt ${result.attempts} of 4. ${4 - result.attempts} attempt${4 - result.attempts !== 1 ? "s" : ""} left`
                  : "Answer revealed. Move to the next question"}
            </p>
          </div>
        </div>

        {/* Hint — attempts 1, 2, 3 */}
        {!result.is_correct && canTryAgain && hintText && (
          <div className="mb-5">
            <HintLevelBadge attempts={result.attempts} />
            <div className="rounded-xl px-4 py-3 text-sm text-stone-900/80 leading-relaxed"
              style={{ background: hintBg.bg, border: `1px solid ${hintBg.border}` }}>
              {hintText}
            </div>
          </div>
        )}

        {/* Final wrong */}
        {isFinalWrong && (
          <div className="mb-5">
            {correctDisplayKey && (
              <p className="text-red-700 font-bold text-sm mb-2 flex items-center gap-1.5">
                <XIcon className="w-3.5 h-3.5 shrink-0" />
                Correct answer: <span className="text-stone-900 bg-red-500/20 px-2 py-0.5 rounded font-mono">{correctDisplayKey}</span>
                {correctAnswerText && <span className="text-stone-900/80 font-medium">{correctAnswerText}</span>}
              </p>
            )}
            {finalExplanation && (
              <div className="rounded-xl bg-orange-900/5 border border-orange-900/15 px-4 py-3">
                <p className="text-stone-500 text-xs font-bold uppercase tracking-wide mb-1">Explanation</p>
                <p className="text-stone-900/70 text-sm leading-relaxed whitespace-pre-line">{finalExplanation}</p>
              </div>
            )}
          </div>
        )}

        {/* Correct — use the shuffled display key, never the backend's internal key. */}
        {result.is_correct && (
          <div className="mb-1">
            {correctDisplayKey && (
              <p className="text-emerald-700 font-bold text-sm mb-3 flex items-center gap-1.5">
                <CheckIcon className="w-3.5 h-3.5 shrink-0" />
                Correct answer: <span className="text-stone-900 bg-emerald-500/20 px-2 py-0.5 rounded font-mono">{correctDisplayKey}</span>
                {correctAnswerText && <span className="text-stone-900/80 font-medium">{correctAnswerText}</span>}
              </p>
            )}
            {finalExplanation && (
              <div className="rounded-xl bg-orange-900/5 border border-orange-900/15 px-4 py-3">
                <p className="text-stone-500 text-xs font-bold uppercase tracking-wide mb-1">Explanation</p>
                <p className="text-stone-900/70 text-sm leading-relaxed whitespace-pre-line">{finalExplanation}</p>
              </div>
            )}
          </div>
        )}

        {/* Try Again — only for hints, no Next here */}
        {canTryAgain && !isRetrying && (
          <div className="mt-5">
            <button id="btn-try-again" onClick={onTryAgain}
              className="w-full py-3 rounded-xl font-bold text-stone-900 transition-all duration-200"
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
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-orange-900/5 text-stone-500 border border-orange-900/15">
          <TagIcon className="w-3 h-3" /> {question.topic}
        </span>
        <BloomBadge level={question.bloom_level} />
        <DifficultyBadge score={question.difficulty} />
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-orange-600/10 text-orange-600/60 border border-orange-600/20">
          <LockIcon className="w-3 h-3" /> Reviewed
        </span>
      </div>
      <p className="text-stone-900 text-xl font-semibold leading-relaxed mb-8">{question.question}</p>
      {opts && (
        <div className="space-y-3">
          {shuffledKeys.map((origKey, idx) => {
            const displayKey = String(idx + 1);
            const optText = opts[origKey as keyof typeof opts];
            const userPicked = record.selectedDisplayKey === displayKey;
            const isAnswerKey = result.correct_answer
              ? result.correct_answer === origKey
              : result.is_correct
                ? userPicked
                : !!result.feedback?.includes(`**${origKey} -`);
            let bg = "rgba(0,0,0,0.03)";
            let border = "rgba(0,0,0,0.08)";
            let labelBg = "rgba(0,0,0,0.06)";
            let labelColor = "rgba(0,0,0,0.5)";
            if (isAnswerKey) { bg = "rgba(52,211,153,0.1)"; border = "rgba(52,211,153,0.3)"; labelBg = "rgba(52,211,153,0.2)"; labelColor = "#34d399"; }
            else if (userPicked) { bg = "rgba(239,68,68,0.1)"; border = "rgba(239,68,68,0.3)"; labelBg = "rgba(239,68,68,0.2)"; labelColor = "#f87171"; }
            return (
              <div key={origKey} className="flex items-center gap-4 px-5 py-4 rounded-xl border" style={{ background: bg, borderColor: border }}>
                <span className="w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold shrink-0" style={{ background: labelBg, color: labelColor }}>{displayKey}</span>
                <span className="text-sm font-medium text-stone-900/70">{optText}</span>
                {isAnswerKey && (
                  <span className="ml-auto text-emerald-600 text-xs font-bold flex items-center gap-1">
                    <CheckIcon className="w-3 h-3" /> Correct
                  </span>
                )}
                {userPicked && !isAnswerKey && (
                  <span className="ml-auto text-red-600 text-xs font-bold flex items-center gap-1">
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
        <p className="text-stone-900/60 text-sm leading-relaxed">{result.feedback}</p>
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
        background: disabled ? "rgba(0,0,0,0.02)" : "rgba(0,0,0,0.06)",
        borderColor: disabled ? "rgba(0,0,0,0.04)" : "rgba(255,255,255,0.12)",
        color: disabled ? "rgba(0,0,0,0.15)" : "rgba(0,0,0,0.7)",
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
  const [waitingForNext, setWaitingForNext] = useState(false);
  const [startTime, setStartTime] = useState(Date.now());
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const submitGuardRef = useRef(false);

  // Answered question history for prev navigation
  const [history, setHistory] = useState<AnsweredRecord[]>([]);
  // -1 = live current question; >=0 = reviewing history[viewIndex]
  const [viewIndex, setViewIndex] = useState<number>(-1);

  // Stable shuffled option keys for current question (seeded by q_id)
  const shuffledKeys = useMemo<string[]>(() => {
    if (!question?.options) return ["1", "2", "3", "4", "5"];
    return seededShuffle(["1", "2", "3", "4", "5"], question.q_id);
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
        setError("");
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

  const recoverCurrentQuestion = async () => {
    // The backend reported the held question as outdated because the real
    // next question was still being generated in the background at the
    // moment of submission. That generation is still running — poll fast at
    // first, then keep trying patiently for a few minutes rather than
    // telling the student to manually retry a few seconds later.
    const fastDelays = [250, 600, 1000, 1800, 3000, 5000];
    const steadyDelayMs = 5000;
    const maxSteadyPolls = 30; // ~2.5 more minutes after the fast ramp
    for (let i = 0; i < fastDelays.length + maxSteadyPolls; i++) {
      try {
        const q = await getCurrentQuestion(sessionId);
        setQuestion(q);
        setResult(null);
        setIsRetrying(false);
        setSelectedDisplayKey(null);
        setViewIndex(-1);
        setError("");
        setStartTime(Date.now());
        return true;
      } catch {
        const delay = i < fastDelays.length ? fastDelays[i] : steadyDelayMs;
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    }
    return false;
  };

  const handleSubmit = async () => {
    if (!selectedDisplayKey || !question || submitGuardRef.current) return;
    submitGuardRef.current = true;
    setSubmitting(true);
    setError("");
    const timeSec = Math.round((Date.now() - startTime) / 1000);
    // Map display position → original answer key for backend
    const dispIdx = Number(selectedDisplayKey) - 1;
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
      const message = e instanceof Error ? e.message : "Submission failed";
      if (/no active question|outdated question/i.test(message)) {
        const recovered = await recoverCurrentQuestion();
        if (!recovered) {
          setError("Your answer was saved, but the next question is still being prepared. Please try again shortly.");
        }
      } else {
        setError(message);
      }
    } finally {
      submitGuardRef.current = false;
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
    setWaitingForNext(true);
    // The next question is generated in the background after the previous
    // answer was submitted (LLM call plus grounding validation, sometimes
    // with a retry or two on a cold GPU endpoint). Poll fast at first for the
    // common case, then keep trying patiently for a few minutes instead of
    // flashing a scary "session may still be processing" error while the
    // backend is still legitimately working.
    const fastDelays = [800, 1500, 2500, 3500, 5000, 7000, 8000];
    const steadyDelayMs = 5000;
    const maxSteadyPolls = 30; // ~2.5 more minutes after the fast ramp
    let lastErr: unknown;
    for (let i = 0; i < fastDelays.length + maxSteadyPolls; i++) {
      try {
        const q = await getCurrentQuestion(sessionId);
        setQuestion(q);
        setStartTime(Date.now());
        setWaitingForNext(false);
        return;
      } catch (e) {
        lastErr = e;
        const delay = i < fastDelays.length ? fastDelays[i] : steadyDelayMs;
        await new Promise((res) => setTimeout(res, delay));
      }
    }
    setWaitingForNext(false);
    setError(lastErr instanceof Error ? lastErr.message : "Could not load next question.");
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
            <div className="brand-mark w-7 h-7 rounded-lg">
              <span className="font-bold text-xs">AQ</span>
            </div>
            <span className="font-bold text-base text-stone-900">AdaptiveIQ</span>
          </Link>
          <span className="text-sm text-stone-500">
            {isViewingHistory
              ? <span className="text-orange-700/60">Reviewing Q{displayedQNum}</span>
              : `Question ${question.q_index + 1} of ${question.total_questions}`}
          </span>
        </div>

        {/* Progress bar */}
        <div className="w-full h-1.5 rounded-full bg-orange-900/10 mb-8 overflow-hidden">
          <div className="h-full rounded-full transition-all duration-500"
            style={{ width: `${progress}%`, background: "linear-gradient(90deg, #d8653b, #ad7b54)" }} />
        </div>

        {/* Review banner */}
        {isViewingHistory && (
          <div className="mb-4 px-4 py-2.5 rounded-xl border border-orange-600/20 bg-orange-600/5 flex items-center gap-2">
            <span className="text-orange-700 text-xs font-semibold flex items-center gap-1.5">
              <EyeIcon className="w-3.5 h-3.5" /> Reviewing Q{displayedQNum}
            </span>
            <span className="text-stone-400 text-xs">Read only</span>
          </div>
        )}

        {/* Question card */}
        <div className="glass-card p-[22px] mb-6 animate-[fadeIn_0.4s_ease-out]"
          style={{ borderColor: isViewingHistory ? "rgba(216,101,59,0.28)" : undefined }}>
          {isViewingHistory ? (
            <PreviousQuestionView record={history[viewIndex]} />
          ) : (
            <>
              {/* Meta */}
              <div className="flex items-center gap-3 mb-6 flex-wrap">
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-orange-900/5 text-stone-500 border border-orange-900/15">
                  <TagIcon className="w-3 h-3" /> {question.topic}
                </span>
                <BloomBadge level={question.bloom_level} />
                <DifficultyBadge score={question.difficulty} />
                {question.is_flagged && (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-700 border border-amber-500/25">
                    <AlertTriangleIcon className="w-3 h-3" /> Low grounding
                  </span>
                )}
              </div>
              <p className="text-stone-900 text-xl font-semibold leading-relaxed mb-8">{question.question}</p>

              {/* MCQ options — shuffled display */}
              {question.q_type === "mcq" && question.options && (
                <div className="space-y-3">
                  {shuffledKeys.map((origKey, idx) => {
                    const displayKey = String(idx + 1);
                    const opt = question.options![origKey as keyof typeof question.options];
                    const selected = selectedDisplayKey === displayKey;
                    return (
                      <button key={origKey} id={`option-${displayKey}`}
                        onClick={() => (!result || isRetrying) && setSelectedDisplayKey(displayKey)}
                        disabled={!!result && !isRetrying}
                        aria-pressed={selected}
                        className="w-full text-left flex items-center gap-4 px-5 py-4 rounded-xl border transition-all duration-200"
                        style={{
                          background: selected ? "rgba(216,101,59,0.12)" : "rgba(255,252,246,0.64)",
                          borderColor: selected ? "rgba(216,101,59,0.55)" : "rgba(97,70,52,0.14)",
                          transform: selected ? "translateX(2px)" : "translateX(0)",
                          cursor: (result && !isRetrying) ? "default" : "pointer",
                        }}>
                        <span className="w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold shrink-0"
                          style={{ background: selected ? "#d8653b" : "rgba(97,70,52,0.07)", color: selected ? "#fffaf3" : "rgba(53,45,39,0.62)" }}>
                          {displayKey}
                        </span>
                        <span className={`text-sm font-medium ${selected ? "text-stone-900" : "text-stone-900/70"}`}>{opt}</span>
                      </button>
                    );
                  })}
                </div>
              )}

              {question.q_type === "fill_blank" && (
                <div>
                  <label htmlFor="fill-blank-answer" className="section-label block mb-2">Exact answer</label>
                  <input
                    id="fill-blank-answer"
                    type="text"
                    autoComplete="off"
                    value={selectedDisplayKey ?? ""}
                    placeholder="Type the exact missing word or phrase"
                    className="input-glass min-h-[52px]"
                    onChange={(e) => setSelectedDisplayKey(e.target.value)}
                    disabled={!!result && !isRetrying}
                  />
                  <p className="mt-2 text-xs text-stone-500">Capital letters do not matter. The word or phrase itself must match exactly.</p>
                </div>
              )}

              {/* Essay / structured */}
              {(question.q_type === "structured" || question.q_type === "essay") && (
                <textarea id="essay-answer" placeholder="Type your answer here..."
                  className="w-full min-h-[160px] rounded-xl px-4 py-3 text-stone-900 placeholder-white/30 border border-orange-900/15 bg-orange-900/5 backdrop-blur-sm outline-none focus:border-orange-600/60 text-sm leading-relaxed resize-none transition-all duration-200"
                  onChange={(e) => setSelectedDisplayKey(e.target.value)} disabled={!!result && !isRetrying} />
              )}
            </>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 rounded-xl px-4 py-3 border border-red-500/30 bg-red-500/10 text-red-700 text-sm flex items-center gap-2">
            <AlertTriangleIcon className="w-4 h-4 shrink-0" /> {error}
          </div>
        )}

        {/* ── Nav bar — always visible ──────────────────────────── */}
        {isViewingHistory ? (
          /* History nav */
          <div className="flex items-center gap-3 mb-4">
            <NavBtn id="btn-hist-prev" disabled={viewIndex <= 0} onClick={() => setViewIndex((v) => v - 1)}><ArrowLeftIcon /> Prev</NavBtn>
            <button id="btn-hist-return" onClick={() => setViewIndex(-1)}
              className="flex-1 py-4 rounded-xl font-semibold text-stone-900/80 text-sm transition-all duration-200 border flex items-center justify-center gap-2"
              style={{ background: "rgba(224,108,79,0.12)", borderColor: "rgba(224,108,79,0.3)" }}>
              <ArrowLeftIcon className="w-4 h-4" /> Back to Current Question
            </button>
            <NavBtn id="btn-hist-next" disabled={false} onClick={() => setViewIndex((v) => v >= history.length - 1 ? -1 : v + 1)}>Next <ArrowRightIcon /></NavBtn>
          </div>
        ) : !answerResolved ? (
          /* Submit bar */
          <div className="flex items-center gap-3 mb-4">
            <NavBtn id="btn-prev-question" disabled={history.length === 0} onClick={() => setViewIndex(history.length - 1)}><ArrowLeftIcon /> Prev</NavBtn>
            <button id="btn-submit-answer" onClick={handleSubmit} disabled={!selectedDisplayKey || submitting}
              className="flex-1 py-4 rounded-xl font-bold text-white text-base transition-all duration-200"
              style={{
                background: !selectedDisplayKey || submitting ? "rgba(0,0,0,0.06)" : "linear-gradient(135deg, #e06c4f, #cc5234)",
                boxShadow: selectedDisplayKey && !submitting ? "0 4px 20px rgba(224,108,79,0.4)" : "none",
                cursor: !selectedDisplayKey || submitting ? "not-allowed" : "pointer",
              }}>
              {submitting ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Checking answer...
                </span>
              ) : <span className="flex items-center justify-center gap-2">Submit Answer <ArrowRightIcon /></span>}
            </button>
            <NavBtn id="btn-next-disabled" disabled={true} onClick={() => {}}>Next <ArrowRightIcon /></NavBtn>
          </div>
        ) : (
          /* After answer resolved */
          <div className="flex items-center gap-3 mb-4">
            <NavBtn id="btn-prev-after" disabled={history.length === 0} onClick={() => setViewIndex(history.length - 1)}><ArrowLeftIcon /> Prev</NavBtn>
            <button id="btn-next-question" onClick={handleNextQuestion} disabled={waitingForNext}
              className="flex-1 py-4 rounded-xl font-bold text-white text-base transition-all duration-200"
              style={{
                background: waitingForNext
                  ? "rgba(0,0,0,0.15)"
                  : result?.quiz_complete ? "linear-gradient(135deg, #059669, #0891b2)" : "linear-gradient(135deg, #e06c4f, #cc5234)",
                boxShadow: waitingForNext ? "none" : `0 4px 20px ${result?.quiz_complete ? "rgba(5,150,105,0.3)" : "rgba(224,108,79,0.4)"}`,
                cursor: waitingForNext ? "not-allowed" : "pointer",
              }}>
              {waitingForNext ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Preparing your next question...
                </span>
              ) : (
                <span className="flex items-center justify-center gap-2">
                  {result?.quiz_complete ? "View Results" : "Next Question"} <ArrowRightIcon />
                </span>
              )}
            </button>
          </div>
        )}

        {/* Adaptive difficulty dots */}
        {isLive && (
          <div className="mt-2 flex items-center justify-center gap-2">
            <span className="text-xs text-stone-400">Adaptive difficulty</span>
            <div className="flex gap-1">
              {[1, 2, 3].map((n) => (
                <div key={n} className="w-1.5 h-1.5 rounded-full" style={{
                  background:
                    question.difficulty < 0.33 && n === 1 ? "#34d399"
                      : question.difficulty >= 0.33 && question.difficulty < 0.66 && n <= 2 ? "#fbbf24"
                        : question.difficulty >= 0.66 && n <= 3 ? "#f87171"
                          : "rgba(0,0,0,0.1)",
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
