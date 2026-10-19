"use client";

import { useEffect, useState, useRef, useCallback, useMemo } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import AppHeader from "@/components/ui/AppHeader";
import { advanceQuestion, getSessionStatus, getCurrentQuestion, submitAnswer, retryQuestionGeneration } from "@/lib/api";
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
function ProcessingScreen({ status, onRetry }: { status: SessionStatusResponse | null; onRetry: () => void }) {
  const isReady = status?.status === "ready";
  const isError = status?.status === "error";
  const topicSession = status?.is_topic_session === true;
  const steps = topicSession
    ? [{ label: "Preparing your topic questions", done: isReady }]
    : [
      { label: "Study material selected", done: true },
      { label: "Reading your material", done: isReady || (status?.chunk_count ?? 0) > 0 },
      { label: "Finding the key concepts", done: isReady || (status?.topics_detected?.length ?? 0) > 0 },
      { label: "Preparing your questions", done: isReady },
    ];
  return (
    <main className="min-h-screen">
      <AppHeader><Link href="/upload" className="editorial-link text-sm">Choose material <ArrowRightIcon /></Link></AppHeader>
      <section className="status-panel animate-fade-in" aria-live="polite">
        <p className="section-label mb-6">Your adaptive quiz</p>
        <div className="mb-6">
          {isError ? <AlertTriangleIcon className="w-8 h-8 text-[var(--warning)]" /> : <span className="block w-8 h-8 rounded-full border-2 border-[var(--border)] border-t-[var(--text)] animate-spin" />}
        </div>
        <h1 className="page-heading mb-5">{isError ? "Let's try that again." : isReady ? "You're ready to begin." : "A little preparation. A better challenge."}</h1>
        <p className="text-[var(--text-muted)] text-base leading-relaxed mb-8">{isError ? status?.message : "We're preparing questions from your chosen material. Your quiz will appear here when it's ready."}</p>
        {isError ? <div className="flex flex-wrap gap-3">
          <button type="button" className="btn-primary" onClick={onRetry}><RefreshIcon /> Retry this quiz</button>
          <Link href="/upload" className="btn-secondary">Choose material</Link>
        </div> : <div className="border-t border-[var(--border)]">
          {steps.map((step) => <div key={step.label} className="flex items-center justify-between gap-4 py-4 border-b border-[var(--border)] text-sm">
            <span>{step.label}</span>{step.done ? <CheckIcon className="w-4 h-4 text-[var(--success)]" /> : <span className="text-[var(--text-dim)] text-xs">In progress</span>}
          </div>)}
        </div>}
      </section>
    </main>
  );
}

// ── Hint level badge — attempt 1=Hard, 2=Medium, 3=Easy ─────────
function HintLevelBadge({ attempts }: { attempts: number }) {
  const levels: Record<number, { label: string; color: string; desc: string }> = {
    1: { label: "Hard Hint",   color: "var(--danger)", desc: "Connect ideas and test your assumptions" },
    2: { label: "Medium Hint", color: "var(--warning)", desc: "Build your own reasoning with a little guidance" },
    3: { label: "Easy Hint",   color: "var(--success)", desc: "Revisit your notes, then try independently" },
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
  questionType,
}: {
  result: SubmitAnswerResponse;
  onTryAgain: () => void;
  shuffledKeys: string[];
  isRetrying: boolean;
  questionType: Question["q_type"];
}) {
  const isOpenEnded = questionType === "structured" || questionType === "essay";
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
    if (isOpenEnded) return null;
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
            ? "var(--surface)"
            : canTryAgain
              ? "var(--surface)"
              : "var(--surface)",
          borderColor: result.is_correct
            ? "rgba(52,211,153,0.3)"
            : canTryAgain ? "rgba(251,191,36,0.3)" : "rgba(248,113,113,0.3)",

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
              <div className="rounded-xl bg-[var(--surface)] border border-[var(--border)] px-4 py-3">
                <p className="text-stone-500 text-xs font-bold uppercase tracking-wide mb-1">
                  {isOpenEnded ? "Model answer" : "Explanation"}
                </p>
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
              <div className="rounded-xl bg-[var(--surface)] border border-[var(--border)] px-4 py-3">
                <p className="text-stone-500 text-xs font-bold uppercase tracking-wide mb-1">
                  {isOpenEnded ? "Model answer" : "Explanation"}
                </p>
                <p className="text-stone-900/70 text-sm leading-relaxed whitespace-pre-line">{finalExplanation}</p>
              </div>
            )}
          </div>
        )}

        {/* Try Again — only for hints, no Next here */}
        {canTryAgain && !isRetrying && (
          <div className="mt-5">
            <button id="btn-try-again" onClick={onTryAgain}
              className="w-full py-3 rounded-xl font-bold text-[var(--background)] transition-all duration-200"
              style={{ background: "var(--primary)", boxShadow: "none" }}>
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
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-[var(--surface)] text-stone-500 border border-[var(--border)]">
          <TagIcon className="w-3 h-3" /> {question.topic}
        </span>
        <BloomBadge level={question.bloom_level} />
        <DifficultyBadge score={question.difficulty} />
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-orange-600/10 text-orange-600/60 border border-orange-600/20">
          <LockIcon className="w-3 h-3" /> Reviewed
        </span>
      </div>
      <p className={`question-stem mb-8 ${question.q_type === "structured" || question.q_type === "essay" ? "whitespace-pre-line" : ""}`}>{question.question}</p>
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
            let labelColor = "var(--text-muted)";
            if (isAnswerKey) { bg = "rgba(52,211,153,0.1)"; border = "rgba(52,211,153,0.3)"; labelBg = "rgba(52,211,153,0.2)"; labelColor = "var(--success)"; }
            else if (userPicked) { bg = "rgba(239,68,68,0.1)"; border = "rgba(239,68,68,0.3)"; labelBg = "rgba(239,68,68,0.2)"; labelColor = "var(--danger)"; }
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
      {!opts && (
        <div className="rounded-xl px-5 py-4 border border-[var(--border)] bg-[var(--surface)]">
          <p className="text-xs font-bold uppercase tracking-wide text-stone-400 mb-2">Your answer</p>
          <p className="text-sm text-stone-900/80 leading-relaxed whitespace-pre-line">
            {record.selectedDisplayKey || "(no answer submitted)"}
          </p>
        </div>
      )}
      <div className="mt-4 px-4 py-3 rounded-xl border"
        style={{ background: result.is_correct ? "rgba(52,211,153,0.07)" : "rgba(239,68,68,0.07)", borderColor: result.is_correct ? "rgba(52,211,153,0.2)" : "rgba(239,68,68,0.2)" }}>
        <p className="text-stone-900/60 text-sm leading-relaxed whitespace-pre-line">{result.feedback}</p>
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
        background: disabled ? "var(--surface-soft)" : "var(--surface)",
        borderColor: "var(--border)",
        color: disabled ? "var(--text-dim)" : "var(--text)",
        opacity: disabled ? .55 : 1,
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
      if (status.status === "completed") {
        if (pollingRef.current) clearInterval(pollingRef.current);
        router.replace(`/quiz/${sessionId}/results`);
      } else if (status.status === "ready") {
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
  }, [sessionId, router]);

  const retrySetup = async () => {
    setError("");
    setSessionStatus((previous) => previous ? { ...previous, status: "processing", message: "Preparing your quiz again?" } : previous);
    try {
      await retryQuestionGeneration(sessionId);
      if (pollingRef.current) clearInterval(pollingRef.current);
      pollingRef.current = setInterval(pollStatus, 1000);
      await pollStatus();
    } catch (err) {
      setSessionStatus((previous) => previous ? { ...previous, status: "error", message: err instanceof Error ? err.message : "Please try again." } : previous);
    }
  };

  useEffect(() => {
    pollStatus();
    pollingRef.current = setInterval(pollStatus, 1000);
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
    if (!question) return;
    const openEnded = question.q_type === "structured" || question.q_type === "essay";
    const needsAdvance = openEnded && (!result || (!result.is_correct && result.attempts < 4));
    setWaitingForNext(true);
    if (needsAdvance) {
      try {
        const advanced = await advanceQuestion(sessionId, question.q_id);
        const finalizedResult = advanced.result;
        setHistory((prev) => prev.some((item) => item.question.q_id === question.q_id)
          ? prev
          : [...prev, {
              question,
              shuffledKeys,
              selectedDisplayKey: selectedDisplayKey ?? "",
              result: finalizedResult,
            }]
        );
        if (advanced.quiz_complete) {
          router.push(`/quiz/${sessionId}/results`);
          return;
        }
      } catch (e) {
        setWaitingForNext(false);
        setError(e instanceof Error ? e.message : "Could not advance to the next question.");
        return;
      }
    }
    setResult(null);
    setIsRetrying(false);
    setSelectedDisplayKey(null);
    setError("");
    setViewIndex(-1);
    // The next question is generated in the background after the previous
    // answer was submitted (LLM call plus grounding validation, sometimes
    // with a retry or two on a cold GPU endpoint). Poll fast at first for the
    // common case, then keep trying patiently for a few minutes instead of
    // flashing a scary "session may still be processing" error while the
    // backend is still legitimately working.
    const fastDelays = [250, 500, 750, 1000, 1000, 1000, 1000];
    const steadyDelayMs = 1000;
    const maxSteadyPolls = 150; // Allow slower extraction without slowing readiness detection.
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
  if (!question) return <ProcessingScreen status={sessionStatus} onRetry={retrySetup} />;

  const isViewingHistory = viewIndex >= 0;
  const isLive = viewIndex === -1;
  const isOpenEnded = question.q_type === "structured" || question.q_type === "essay";
  const answerResolved = !!result && !isRetrying && (
    isOpenEnded || result.is_correct || result.attempts >= 4
  );

  const progress = ((question.q_index + 1) / question.total_questions) * 100;
  const displayedQNum = isViewingHistory ? history[viewIndex].question.q_index + 1 : question.q_index + 1;

  return (
    <main className="quiz-page min-h-screen">
      <AppHeader><Link href="/upload" className="editorial-link text-sm">New quiz <ArrowRightIcon /></Link></AppHeader>
      <div className="quiz-content max-w-3xl mx-auto">

        <div className="quiz-section-label"><span className="section-label">{isViewingHistory ? `Reviewing question ${displayedQNum}` : `Question ${question.q_index + 1} of ${question.total_questions}`}</span><span className="section-label">Your practice</span></div>

        {/* Progress bar */}
        <div className="w-full h-1.5 rounded-full bg-orange-900/10 mb-8 overflow-hidden">
          <div className="h-full rounded-full transition-all duration-500"
            style={{ width: `${progress}%`, background: "var(--accent)" }} />
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
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-[var(--surface)] text-stone-500 border border-[var(--border)]">
                  <TagIcon className="w-3 h-3" /> {question.topic}
                </span>
                <BloomBadge level={question.bloom_level} />
                <DifficultyBadge score={question.difficulty} />
                {question.grounding_status === "topic_model" && (
                <span className="badge-cyan">Syllabus practice</span>
              )}
              {question.is_flagged && (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-700 border border-amber-500/25">
                    <AlertTriangleIcon className="w-3 h-3" /> Low grounding
                  </span>
                )}
              </div>
              <p className={`question-stem mb-8 ${question.q_type === "structured" || question.q_type === "essay" ? "whitespace-pre-line" : ""}`}>{question.question}</p>

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
                          background: selected ? "var(--canvas)" : "var(--surface)",
                          borderColor: selected ? "var(--text)" : "var(--border)",

                          cursor: (result && !isRetrying) ? "default" : "pointer",
                        }}>
                        <span className="w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold shrink-0"
                          style={{ background: selected ? "var(--primary)" : "rgba(97,70,52,0.07)", color: selected ? "var(--background)" : "var(--text-muted)" }}>
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
                  className="w-full min-h-[160px] rounded-xl px-4 py-3 text-stone-900 placeholder-white/30 border border-[var(--border)] bg-[var(--surface)]  outline-none focus:border-orange-600/60 text-sm leading-relaxed resize-none transition-all duration-200"
                  value={selectedDisplayKey ?? ""}
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
              className="flex-1 py-4 rounded-xl font-bold text-[var(--background)] text-base transition-all duration-200"
              style={{
                background: !selectedDisplayKey || submitting ? "var(--canvas)" : "var(--primary)",
                color: !selectedDisplayKey || submitting ? "var(--text-dim)" : "var(--background)",
                boxShadow: "none",
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
            <NavBtn
              id={isOpenEnded ? "btn-next-open-ended" : "btn-next-disabled"}
              disabled={!isOpenEnded || waitingForNext}
              onClick={handleNextQuestion}
            >
              {waitingForNext ? "Preparing..." : "Next"} <ArrowRightIcon />
            </NavBtn>
          </div>
        ) : (
          /* After answer resolved */
          <div className="flex items-center gap-3 mb-4">
            <NavBtn id="btn-prev-after" disabled={history.length === 0} onClick={() => setViewIndex(history.length - 1)}><ArrowLeftIcon /> Prev</NavBtn>
            <button id="btn-next-question" onClick={handleNextQuestion} disabled={waitingForNext}
              className="flex-1 py-4 rounded-xl font-bold text-[var(--background)] text-base transition-all duration-200"
              style={{
                background: waitingForNext
                  ? "rgba(0,0,0,0.15)"
                  : result?.quiz_complete ? "var(--primary)" : "var(--primary)",
                boxShadow: "none",
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
                    question.difficulty < 0.33 && n === 1 ? "var(--success)"
                      : question.difficulty >= 0.33 && question.difficulty < 0.66 && n <= 2 ? "var(--warning)"
                        : question.difficulty >= 0.66 && n <= 3 ? "var(--danger)"
                          : "rgba(0,0,0,0.1)",
                }} />
              ))}
            </div>
          </div>
        )}

        {/* Feedback card — only on live question */}
        {isLive && result && (
          <FeedbackCard
            result={result}
            onTryAgain={handleTryAgain}
            shuffledKeys={shuffledKeys}
            isRetrying={isRetrying}
            questionType={question.q_type}
          />
        )}
      </div>
    </main>
  );
}
