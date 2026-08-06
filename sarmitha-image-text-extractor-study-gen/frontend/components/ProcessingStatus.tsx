"use client";

import { CheckCircle, Loader2, Sparkles, Type, Upload } from "lucide-react";

export type Step = "idle" | "uploading" | "enhancing" | "extracting" | "done" | "error";

interface Props {
  step: Step;
  errorMessage?: string;
}

const STEPS = [
  {
    id: "uploading",
    label: "Uploading image",
    icon: Upload,
    doneLabel: "Image received",
  },
  {
    id: "enhancing",
    label: "Enhancing with SRCNN",
    icon: Sparkles,
    doneLabel: "Image enhanced (4×)",
  },
  {
    id: "extracting",
    label: "Extracting text with TrOCR",
    icon: Type,
    doneLabel: "Text extracted",
  },
] as const;

type StepId = (typeof STEPS)[number]["id"];

const ORDER: Step[] = ["idle", "uploading", "enhancing", "extracting", "done", "error"];

function stepIndex(s: Step) {
  return ORDER.indexOf(s);
}

export default function ProcessingStatus({ step, errorMessage }: Props) {
  if (step === "idle") return null;

  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-sm">
      <h3 className="mb-5 text-sm font-semibold uppercase tracking-widest text-white/50">
        Processing Pipeline
      </h3>

      <div className="flex flex-col gap-4">
        {STEPS.map((s) => {
          const currentIdx = stepIndex(step);
          const sIdx = stepIndex(s.id as Step);
          const isActive = step === s.id;
          const isDone = currentIdx > sIdx && step !== "error";
          const isPending = currentIdx < sIdx;
          const Icon = s.icon;

          return (
            <div key={s.id} className="flex items-center gap-4">
              {/* Icon */}
              <div
                className={`
                  flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition-all duration-300
                  ${isDone ? "bg-emerald-500/20" : ""}
                  ${isActive ? "bg-violet-500/20 ring-2 ring-violet-500/40" : ""}
                  ${isPending ? "bg-white/5" : ""}
                `}
              >
                {isDone ? (
                  <CheckCircle className="h-5 w-5 text-emerald-400" />
                ) : isActive ? (
                  <Loader2 className="h-5 w-5 animate-spin text-violet-400" />
                ) : (
                  <Icon
                    className={`h-5 w-5 ${isPending ? "text-white/20" : "text-white/60"}`}
                  />
                )}
              </div>

              {/* Label */}
              <div className="flex-1">
                <p
                  className={`text-sm font-medium transition-colors duration-200
                    ${isDone ? "text-emerald-400" : ""}
                    ${isActive ? "text-violet-300" : ""}
                    ${isPending ? "text-white/30" : ""}
                  `}
                >
                  {isDone ? s.doneLabel : s.label}
                </p>
              </div>

              {/* Active pulse badge */}
              {isActive && (
                <span className="inline-flex items-center gap-1 rounded-full bg-violet-500/20 px-2.5 py-0.5 text-xs font-medium text-violet-300">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-violet-400" />
                  Running
                </span>
              )}
              {isDone && (
                <span className="text-xs text-emerald-500">✓</span>
              )}
            </div>
          );
        })}
      </div>

      {/* Error state */}
      {step === "error" && errorMessage && (
        <div className="mt-5 rounded-xl border border-red-500/20 bg-red-500/10 p-4">
          <p className="text-sm font-medium text-red-400">Error</p>
          <p className="mt-1 text-sm text-red-300/80">{errorMessage}</p>
        </div>
      )}
    </div>
  );
}
