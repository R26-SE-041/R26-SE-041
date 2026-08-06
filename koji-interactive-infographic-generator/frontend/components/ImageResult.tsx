// frontend/components/ImageResult.tsx
// Result display card: generated image + enhanced prompt + eval scores

"use client";

import React from "react";

export interface EvalScores {
  clip_score: number | null;
  vlm_score: number | null;
  vlm_feedback: string | null;
}

export interface ImageResultProps {
  imageSrc: string;           // base64 data URI  e.g. "data:image/png;base64,..."
  enhancedPrompt: string | null;
  evalScores: EvalScores;
  dbRecordId: string | null;
  partialError: string | null; // non-null = pipeline ran but something partially failed
}

// ── Score bar component ───────────────────────────────────────────────────────

function ScoreBar({
  label,
  value,
  max,
  hint,
}: {
  label: string;
  value: number | null;
  max: number;
  hint: string;
}) {
  const pct = value !== null ? Math.min((value / max) * 100, 100) : 0;
  const displayVal = value !== null ? value.toFixed(1) : "—";

  // Color: green above 70%, amber 40-70%, red below 40%
  const barColor =
    value === null
      ? "rgba(255,255,255,0.08)"
      : pct >= 70
      ? "linear-gradient(90deg, #34d399, #6ee7b7)"
      : pct >= 40
      ? "linear-gradient(90deg, #fbbf24, #f59e0b)"
      : "linear-gradient(90deg, #f87171, #fb923c)";

  return (
    <div style={{ marginBottom: "16px" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginBottom: "6px",
        }}
      >
        <span
          style={{
            fontSize: "0.82rem",
            fontWeight: 500,
            color: "#a0a0c0",
          }}
        >
          {label}
        </span>
        <span
          style={{
            fontSize: "0.82rem",
            fontWeight: 600,
            color: "#f0f0ff",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {displayVal}
          <span style={{ color: "#60607a", fontWeight: 400, fontSize: "0.75rem" }}>
            /{max}
          </span>
        </span>
      </div>

      {/* Track */}
      <div
        style={{
          height: "6px",
          background: "rgba(255,255,255,0.06)",
          borderRadius: "100px",
          overflow: "hidden",
        }}
      >
        {/* Fill */}
        <div
          style={{
            height: "100%",
            width: `${pct}%`,
            background: barColor,
            borderRadius: "100px",
            transition: "width 0.8s cubic-bezier(0.16,1,0.3,1)",
          }}
        />
      </div>

      <p style={{ fontSize: "0.72rem", color: "#60607a", marginTop: "4px" }}>
        {hint}
      </p>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ImageResult({
  imageSrc,
  enhancedPrompt,
  evalScores,
  dbRecordId,
  partialError,
}: ImageResultProps) {
  return (
    <div
      style={{
        animation: "fadeSlideUp 0.5s cubic-bezier(0.16,1,0.3,1) forwards",
      }}
    >
      <style>{`
        @keyframes fadeSlideUp {
          from { opacity: 0; transform: translateY(20px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      {/* Partial error notice */}
      {partialError && (
        <div className="error-banner" style={{ marginBottom: "20px" }}>
          <strong>⚠ Partial pipeline failure</strong>
          {partialError}
        </div>
      )}

      {/* Generated image */}
      <div className="glass-card" style={{ marginBottom: "20px", overflow: "hidden" }}>
        <div
          style={{
            padding: "8px 8px 0",
          }}
        >
          <img
            id="generated-image"
            src={imageSrc}
            alt="AI-generated educational image"
            style={{
              width: "100%",
              borderRadius: "16px",
              display: "block",
              objectFit: "cover",
            }}
          />
        </div>

        {/* Enhanced prompt below image */}
        {enhancedPrompt && (
          <div style={{ padding: "20px 24px 24px" }}>
            <p
              style={{
                fontSize: "0.72rem",
                fontWeight: 600,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                color: "#60607a",
                marginBottom: "8px",
              }}
            >
              Enhanced Prompt
            </p>
            <p
              id="enhanced-prompt-text"
              style={{
                fontSize: "0.9rem",
                color: "#a0a0c0",
                lineHeight: 1.65,
                fontStyle: "italic",
              }}
            >
              &ldquo;{enhancedPrompt}&rdquo;
            </p>
          </div>
        )}
      </div>

      {/* Evaluation scores */}
      <div className="glass-card" style={{ padding: "24px" }}>
        <h2
          style={{
            fontSize: "0.72rem",
            fontWeight: 600,
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            color: "#60607a",
            marginBottom: "20px",
          }}
        >
          Evaluation Scores
        </h2>

        <ScoreBar
          label="CLIPScore"
          value={evalScores.clip_score}
          max={35}
          hint="Image-text cosine similarity (typical range: 20–35)"
        />

        <ScoreBar
          label="VLM Score"
          value={evalScores.vlm_score}
          max={10}
          hint="Qwen2.5-VL: prompt alignment + educational usefulness (avg)"
        />

        {evalScores.vlm_feedback && (
          <div
            id="vlm-feedback"
            style={{
              marginTop: "16px",
              padding: "14px 16px",
              background: "rgba(255,255,255,0.03)",
              border: "1px solid rgba(255,255,255,0.06)",
              borderRadius: "10px",
            }}
          >
            <p
              style={{
                fontSize: "0.72rem",
                fontWeight: 600,
                letterSpacing: "0.06em",
                textTransform: "uppercase",
                color: "#60607a",
                marginBottom: "6px",
              }}
            >
              VLM Feedback
            </p>
            <p style={{ fontSize: "0.88rem", color: "#a0a0c0", lineHeight: 1.6 }}>
              {evalScores.vlm_feedback}
            </p>
          </div>
        )}

        {dbRecordId && (
          <p
            style={{
              fontSize: "0.7rem",
              color: "#40405a",
              marginTop: "18px",
              textAlign: "right",
              fontFamily: "monospace",
            }}
          >
            Record: {dbRecordId}
          </p>
        )}
      </div>
    </div>
  );
}
