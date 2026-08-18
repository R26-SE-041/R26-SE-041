"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import { getSessionStatus, getCurrentQuestion, submitAnswer } from "@/lib/api";
import type {
  SessionStatusResponse,
  Question,
  SubmitAnswerResponse,
} from "@/types/quiz";

// ── Difficulty label ────────────────────────────────────────────
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

// ── Processing screen (polling) ─────────────────────────────────
function ProcessingScreen({ status }: { status: SessionStatusResponse | null }) {
  const isReady = status?.status === "ready";
  const isError = status?.status === "error";

  const steps = [
    { id: "upload",    label: "Files uploaded",                     done: true },
    { id: "ingest",    label: "Extracting text chunks",              done: isReady || (status?.chunk_count ?? 0) > 0 },
    { id: "knowledge", label: "Identifying topics",                  done: isReady || (status?.topics_detected?.length ?? 0) > 0 },
    { id: "quiz",      label: "Generating questions with Qwen2.5-7B", done: isReady },
  ];

  if (isError) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="max-w-md w-full text-center">
          <div className="text-6xl mb-6">❌</div>
          <h1 className="text-2xl font-bold text-red-300 mb-3">Setup Failed</h1>
          <p className="text-white/50 text-sm mb-6">{status?.message}</p>
          <a href="/upload" className="inline-block px-6 py-3 rounded-xl font-bold text-white"
            style={{ background: "linear-gradient(135deg, #7c3aed, #4f46e5)" }}>
            ← Try Again
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="max-w-md w-full text-center">
        {/* Spinner ring */}
        <div className="relative w-24 h-24 mx-auto mb-8">
          <div className="absolute inset-0 rounded-full border-4 border-violet-500/20" />
          <div
            className={`absolute inset-0 rounded-full border-4 border-transparent border-t-violet-500 ${
              isReady ? "" : "animate-spin"
            }`}
            style={{ animationDuration: "1.2s" }}
          />
          <div className="absolute inset-3 rounded-full flex items-center justify-center text-3xl">
            {isReady ? "✅" : "🧠"}
          </div>
        </div>

        <h1 className="text-2xl font-bold text-white mb-2">
          {isReady ? "Almost ready!" : "Processing your documents"}
        </h1>
        <p className="text-white/50 text-sm mb-8">{status?.message ?? "Initializing agents..."}</p>

        <div className="space-y-3 text-left">
          {steps.map((step) => (
            <div
              key={step.id}
              className="flex items-center gap-3 px-4 py-3 rounded-xl border"
              style={{
                background: step.done ? "rgba(52,211,153,0.08)" : "rgba(255,255,255,0.03)",
                borderColor: step.done ? "rgba(52,211,153,0.2)" : "rgba(255,255,255,0.08)",
              }}
            >
              <span className="text-lg">{step.done ? "✅" : "⏳"}</span>
              <span className={`text-sm font-medium ${step.done ? "text-emerald-300" : "text-white/40"}`}>
                {step.label}
              </span>
              {!step.done && (
                <span className="ml-auto text-xs text-white/30 animate-pulse">running...</span>
              )}
            </div>
          ))}
        </div>

        {status?.topics_detected && status.topics_detected.length > 0 && (
          <div className="mt-6 text-left">
            <p className="text-xs font-semibold uppercase tracking-widest text-white/30 mb-2">
              Topics detected
            </p>
            <div className="flex flex-wrap gap-2">
              {status.topics_detected.slice(0, 6).map((t) => (
                <span key={t} className="px-2.5 py-1 rounded-full text-xs bg-violet-500/15 text-violet-300 border border-violet-500/25">
                  {t}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Feedback overlay ────────────────────────────────────────────
function FeedbackOverlay({
  result,
  onNext,
  isLast,
}: {
  result: SubmitAnswerResponse;
  onNext: () => void;
  isLast: boolean;
}) {
  const canTryAgain = !result.is_correct && result.attempts < 3;
  const isFinalWrong = !result.is_correct && !canTryAgain;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center px-4 pb-6">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div
        className="relative w-full max-w-lg rounded-2xl p-6 border animate-[slideUp_0.3s_ease-out]"
        style={{
          background: result.is_correct
            ? "linear-gradient(135deg, rgba(16,185,129,0.15), rgba(5,150,105,0.1))"
            : canTryAgain 
              ? "linear-gradient(135deg, rgba(245,158,11,0.15), rgba(217,119,6,0.1))"
              : "linear-gradient(135deg, rgba(239,68,68,0.12), rgba(220,38,38,0.08))",
          borderColor: result.is_correct ? "rgba(52,211,153,0.3)" : canTryAgain ? "rgba(251,191,36,0.3)" : "rgba(248,113,113,0.3)",
          backdropFilter: "blur(16px)",
        }}
      >
        <div className="flex items-center gap-3 mb-4">
          <span className="text-4xl">{result.is_correct ? "🎉" : canTryAgain ? "💡" : "❌"}</span>
          <div>
            <h3 className={`font-bold text-xl ${result.is_correct ? "text-emerald-300" : canTryAgain ? "text-amber-300" : "text-red-300"}`}>
              {result.is_correct ? "Correct!" : canTryAgain ? "Socratic Hint" : "Incorrect"}
            </h3>
            <p className="text-white/50 text-sm">
              Score: {Math.round(result.score * 100)}% {canTryAgain && `| Attempt ${result.attempts}/3`}
            </p>
          </div>
        </div>
        <p className="text-white/70 text-sm leading-relaxed mb-6">{result.feedback}</p>
        <button
          id="btn-next-question"
          onClick={onNext}
          className="w-full py-3 rounded-xl font-bold text-white transition-all duration-200"
          style={{
            background: canTryAgain 
              ? "linear-gradient(135deg, #f59e0b, #d97706)"
              : isLast
                ? "linear-gradient(135deg, #059669, #0891b2)"
                : "linear-gradient(135deg, #7c3aed, #4f46e5)",
            boxShadow: `0 4px 20px ${canTryAgain ? "rgba(245,158,11,0.3)" : isLast ? "rgba(5,150,105,0.3)" : "rgba(124,58,237,0.4)"}`,
          }}
        >
          {canTryAgain ? "Try Again ↻" : isLast ? "View Results →" : "Next Question →"}
        </button>
      </div>
    </div>
  );
}

// ── Main quiz page ──────────────────────────────────────────────
export default function QuizPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string;

  const [sessionStatus, setSessionStatus] = useState<SessionStatusResponse | null>(null);
  const [question, setQuestion] = useState<Question | null>(null);
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<SubmitAnswerResponse | null>(null);
  const [error, setError] = useState("");
  const [startTime, setStartTime] = useState(Date.now());
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Poll for session readiness
  const pollStatus = useCallback(async () => {
    try {
      const status = await getSessionStatus(sessionId);
      setSessionStatus(status);
      if (status.status === "ready") {
        if (pollingRef.current) clearInterval(pollingRef.current);
        // Fetch first question
        const q = await getCurrentQuestion(sessionId);
        setQuestion(q);
        setStartTime(Date.now());
      } else if (status.status === "error") {
        if (pollingRef.current) clearInterval(pollingRef.current);
        setError("Session processing failed. Please try again.");
      }
    } catch {
      setError("Could not connect to server. Is the backend running?");
    }
  }, [sessionId]);

  useEffect(() => {
    pollStatus(); // immediate first call
    pollingRef.current = setInterval(pollStatus, 3000);
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [pollStatus]);

  const handleSubmit = async () => {
    if (!selectedOption || !question) return;
    setSubmitting(true);
    const timeSec = Math.round((Date.now() - startTime) / 1000);
    try {
      const res = await submitAnswer(sessionId, {
        answer: selectedOption,
        time_taken_sec: timeSec,
      });
      setResult(res);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Submission failed";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const handleNext = async () => {
    if (result?.quiz_complete) {
      router.push(`/quiz/${sessionId}/results`);
      return;
    }
    setResult(null);
    setSelectedOption(null);
    setError("");
    try {
      const q = await getCurrentQuestion(sessionId);
      setQuestion(q);
      setStartTime(Date.now());
    } catch {
      setError("Could not load next question.");
    }
  };

  // ── Render: processing ─────────────────────────────────────
  if (!question) {
    return <ProcessingScreen status={sessionStatus} />;
  }

  const progress = question
    ? ((question.q_index + 1) / question.total_questions) * 100
    : 0;

  return (
    <main className="min-h-screen py-8 px-4">
      {/* Feedback overlay */}
      {result && (
        <FeedbackOverlay
          result={result}
          onNext={handleNext}
          isLast={result.quiz_complete}
        />
      )}

      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <Link href="/" className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: "linear-gradient(135deg, #7c3aed, #4f46e5)" }}>
              <span className="text-white font-bold text-xs">AQ</span>
            </div>
            <span className="font-bold text-base text-white">AdaptiveIQ</span>
          </Link>
          <div className="flex items-center gap-3">
            <span className="text-sm text-white/40">
              Question {question.q_index + 1} of {question.total_questions}
            </span>
          </div>
        </div>

        {/* Progress bar */}
        <div className="w-full h-1.5 rounded-full bg-white/10 mb-8 overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${progress}%`,
              background: "linear-gradient(90deg, #8b5cf6, #22d3ee)",
            }}
          />
        </div>

        {/* Question card */}
        <div
          className="rounded-2xl p-8 border mb-6 animate-[fadeIn_0.4s_ease-out]"
          style={{
            background: "rgba(255,255,255,0.04)",
            borderColor: "rgba(255,255,255,0.1)",
            backdropFilter: "blur(12px)",
          }}
        >
          {/* Meta row */}
          <div className="flex items-center gap-3 mb-6 flex-wrap">
            <span className="px-3 py-1 rounded-full text-xs font-semibold bg-white/5 text-white/50 border border-white/10">
              📌 {question.topic}
            </span>
            <BloomBadge level={question.bloom_level} />
            <DifficultyBadge score={question.difficulty} />
            {question.is_flagged && (
              <span className="px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/25">
                ⚠ Low grounding
              </span>
            )}
          </div>

          {/* Question text */}
          <p className="text-white text-xl font-semibold leading-relaxed mb-8">
            {question.question}
          </p>

          {/* MCQ Options */}
          {question.q_type === "mcq" && question.options && (
            <div className="space-y-3">
              {(["A", "B", "C", "D"] as const).map((key) => {
                const opt = question.options![key];
                const selected = selectedOption === key;
                return (
                  <button
                    key={key}
                    id={`option-${key}`}
                    onClick={() => !result && setSelectedOption(key)}
                    disabled={!!result}
                    className="w-full text-left flex items-center gap-4 px-5 py-4 rounded-xl border transition-all duration-200"
                    style={{
                      background: selected ? "rgba(139,92,246,0.2)" : "rgba(255,255,255,0.03)",
                      borderColor: selected ? "rgba(139,92,246,0.6)" : "rgba(255,255,255,0.08)",
                      transform: selected ? "scale(1.01)" : "scale(1)",
                    }}
                  >
                    <span
                      className="w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold shrink-0"
                      style={{
                        background: selected ? "rgba(139,92,246,0.4)" : "rgba(255,255,255,0.06)",
                        color: selected ? "#c4b5fd" : "rgba(255,255,255,0.5)",
                      }}
                    >
                      {key}
                    </span>
                    <span className={`text-sm font-medium ${selected ? "text-white" : "text-white/70"}`}>
                      {opt}
                    </span>
                  </button>
                );
              })}
            </div>
          )}

          {/* Text answer for structured/essay */}
          {question.q_type !== "mcq" && (
            <textarea
              id="essay-answer"
              placeholder="Type your answer here..."
              className="w-full min-h-[160px] rounded-xl px-4 py-3 text-white placeholder-white/30 border border-white/10 bg-white/5 backdrop-blur-sm outline-none focus:border-violet-500/60 text-sm leading-relaxed resize-none transition-all duration-200"
              onChange={(e) => setSelectedOption(e.target.value)}
            />
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 rounded-xl px-4 py-3 border border-red-500/30 bg-red-500/10 text-red-300 text-sm">
            ⚠️ {error}
          </div>
        )}

        {/* Submit button */}
        {!result && (
          <button
            id="btn-submit-answer"
            onClick={handleSubmit}
            disabled={!selectedOption || submitting}
            className="w-full py-4 rounded-xl font-bold text-white text-base transition-all duration-200"
            style={{
              background:
                !selectedOption || submitting
                  ? "rgba(255,255,255,0.06)"
                  : "linear-gradient(135deg, #7c3aed, #4f46e5)",
              boxShadow:
                selectedOption && !submitting
                  ? "0 4px 20px rgba(124,58,237,0.4)"
                  : "none",
              cursor: !selectedOption || submitting ? "not-allowed" : "pointer",
            }}
          >
            {submitting ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Evaluating...
              </span>
            ) : (
              "Submit Answer →"
            )}
          </button>
        )}
      </div>
    </main>
  );
}
