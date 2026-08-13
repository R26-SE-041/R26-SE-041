"use client";

import { CheckCircle, Loader2, ScanText, ImageUp, Upload } from "lucide-react";

export type Step = "idle" | "uploading" | "enhancing" | "extracting" | "done" | "error";

interface Props {
  step: Step;
  errorMessage?: string;
}

const STEPS = [
  {
    id: "uploading",
    label: "Uploading image",
    Icon: Upload,
    doneLabel: "Image received",
  },
  {
    id: "enhancing",
    label: "Enhancing with SRCNN",
    Icon: ImageUp,
    doneLabel: "Image enhanced (4x)",
  },
  {
    id: "extracting",
    label: "Extracting Sinhala text with TrOCR",
    Icon: ScanText,
    doneLabel: "Sinhala text extracted",
  },
] as const;

const ORDER: Step[] = ["idle", "uploading", "enhancing", "extracting", "done", "error"];

function stepIndex(s: Step) {
  return ORDER.indexOf(s);
}

export default function ProcessingStatus({ step, errorMessage }: Props) {
  if (step === "idle") return null;

  const currentIdx = stepIndex(step);

  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="Processing pipeline status"
      style={{
        borderRadius: "1.5rem",
        border: "1px solid rgba(255,255,255,0.08)",
        background: "rgba(255,255,255,0.03)",
        backdropFilter: "blur(12px)",
        WebkitBackdropFilter: "blur(12px)",
        padding: "1.5rem",
      }}
    >
      <h3
        style={{
          marginBottom: "1.25rem",
          fontSize: "0.6875rem",
          fontWeight: 600,
          letterSpacing: "0.1em",
          textTransform: "uppercase",
          color: "rgba(255,255,255,0.35)",
        }}
      >
        Processing Pipeline
      </h3>

      <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        {STEPS.map((s) => {
          const sIdx = stepIndex(s.id as Step);
          const isActive = step === s.id;
          const isDone = currentIdx > sIdx && step !== "error";
          const isPending = currentIdx < sIdx;
          const { Icon } = s;

          let iconBg = "rgba(255,255,255,0.05)";
          let iconColor = "rgba(255,255,255,0.2)";
          if (isDone) { iconBg = "rgba(52,211,153,0.12)"; iconColor = "#34d399"; }
          if (isActive) { iconBg = "rgba(139,92,246,0.15)"; iconColor = "#a78bfa"; }

          let labelColor = "rgba(255,255,255,0.25)";
          if (isDone) labelColor = "#34d399";
          if (isActive) labelColor = "#c4b5fd";

          return (
            <div
              key={s.id}
              id={`pipeline-step-${s.id}`}
              style={{ display: "flex", alignItems: "center", gap: "1rem" }}
            >
              {/* Icon container */}
              <div
                style={{
                  flexShrink: 0,
                  width: "2.25rem",
                  height: "2.25rem",
                  borderRadius: "9999px",
                  background: iconBg,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  boxShadow: isActive ? "0 0 0 2px rgba(139,92,246,0.35)" : "none",
                  transition: "background 300ms ease, box-shadow 300ms ease",
                }}
                aria-hidden="true"
              >
                {isDone ? (
                  <CheckCircle
                    style={{ width: "1.125rem", height: "1.125rem", color: "#34d399" }}
                    strokeWidth={1.75}
                  />
                ) : isActive ? (
                  <Loader2
                    className="animate-spin"
                    style={{ width: "1.125rem", height: "1.125rem", color: "#a78bfa" }}
                    strokeWidth={1.75}
                  />
                ) : (
                  <Icon
                    style={{ width: "1.125rem", height: "1.125rem", color: iconColor }}
                    strokeWidth={1.75}
                  />
                )}
              </div>

              {/* Label */}
              <div style={{ flex: 1 }}>
                <p
                  style={{
                    fontSize: "0.875rem",
                    fontWeight: 500,
                    color: labelColor,
                    transition: "color 200ms ease",
                  }}
                >
                  {isDone ? s.doneLabel : s.label}
                </p>
              </div>

              {/* Status badge */}
              {isActive && (
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "0.375rem",
                    borderRadius: "9999px",
                    background: "rgba(139,92,246,0.15)",
                    padding: "0.125rem 0.625rem",
                    fontSize: "0.6875rem",
                    fontWeight: 500,
                    color: "#c4b5fd",
                  }}
                >
                  <span
                    className="animate-pulse-ring"
                    style={{
                      width: "0.375rem",
                      height: "0.375rem",
                      borderRadius: "9999px",
                      background: "#a78bfa",
                      display: "inline-block",
                    }}
                  />
                  Running
                </span>
              )}
              {isDone && !isPending && (
                <CheckCircle
                  aria-label="Step complete"
                  style={{ width: "1rem", height: "1rem", color: "#34d399", flexShrink: 0 }}
                  strokeWidth={1.75}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Error state */}
      {step === "error" && errorMessage && (
        <div
          role="alert"
          style={{
            marginTop: "1.25rem",
            borderRadius: "0.75rem",
            border: "1px solid rgba(248,113,113,0.2)",
            background: "rgba(248,113,113,0.08)",
            padding: "1rem",
          }}
        >
          <p
            style={{
              fontSize: "0.875rem",
              fontWeight: 600,
              color: "#f87171",
              marginBottom: "0.25rem",
            }}
          >
            Error
          </p>
          <p style={{ fontSize: "0.875rem", color: "rgba(252,165,165,0.75)" }}>
            {errorMessage}
          </p>
        </div>
      )}
    </div>
  );
}
