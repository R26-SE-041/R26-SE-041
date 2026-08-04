// frontend/app/page.tsx
// Full workflow: Enhance (Qwen 2.5-3B) → Generate (FLUX.1-dev) → Interactive (SAM 2 + Qwen2.5-VL)

"use client";

import React, { useState, useEffect } from "react";
import InteractiveCanvas from "@/components/InteractiveCanvas";

const PROMPT_AGENT_URL =
  process.env.NEXT_PUBLIC_PROMPT_AGENT_URL ??
  "https://kojithan-y--prompt-agent-api-dev.modal.run";

const IMAGE_AGENT_URL =
  process.env.NEXT_PUBLIC_IMAGE_AGENT_URL ??
  "https://kojithan-y--image-agent-api-dev.modal.run";

const INTERACTIVE_AGENT_URL =
  process.env.NEXT_PUBLIC_INTERACTIVE_AGENT_URL ??
  "https://kojithan-y--interactive-agent-api-dev.modal.run";

// ── Types ──────────────────────────────────────────────────────────────────────

type Stage = "idle" | "enhancing" | "generating" | "done";
type Mode  = "direct" | "enhance";

// ── Component ──────────────────────────────────────────────────────────────────

export default function HomePage() {
  const [prompt, setPrompt]               = useState("");
  const [stage, setStage]                 = useState<Stage>("idle");
  const [mode, setMode]                   = useState<Mode>("enhance");
  const [enhancedPrompt, setEnhancedPrompt] = useState<string | null>(null);
  const [imageBase64, setImageBase64]     = useState<string | null>(null);
  const [error, setError]                 = useState<string | null>(null);

  const [promptHealth, setPromptHealth]           = useState<"ok"|"error"|"checking">("checking");
  const [imageHealth, setImageHealth]             = useState<"ok"|"error"|"checking">("checking");
  const [interactiveHealth, setInteractiveHealth] = useState<"ok"|"error"|"checking">("checking");

  const isLoading = stage === "enhancing" || stage === "generating";

  // ── Health checks on mount ────────────────────────────────────────────────
  useEffect(() => {
    fetch(`${PROMPT_AGENT_URL}/health`)
      .then(r => r.ok ? setPromptHealth("ok") : setPromptHealth("error"))
      .catch(() => setPromptHealth("error"));

    fetch(`${IMAGE_AGENT_URL}/health`)
      .then(r => r.ok ? setImageHealth("ok") : setImageHealth("error"))
      .catch(() => setImageHealth("error"));

    fetch(`${INTERACTIVE_AGENT_URL}/health`)
      .then(r => r.ok ? setInteractiveHealth("ok") : setInteractiveHealth("error"))
      .catch(() => setInteractiveHealth("error"));
  }, []);

  // ── Helpers ────────────────────────────────────────────────────────────────
  function reset() {
    setStage("idle");
    setEnhancedPrompt(null);
    setImageBase64(null);
    setError(null);
  }

  async function callEnhance(raw: string): Promise<string> {
    const res = await fetch(`${PROMPT_AGENT_URL}/enhance`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ raw_prompt: raw }),
    });
    if (!res.ok) {
      const e = await res.json().catch(() => ({}));
      throw new Error(e?.detail?.error ?? e?.detail ?? `Enhance HTTP ${res.status}`);
    }
    const data = await res.json();
    if (data.error && !data.enhanced_prompt) throw new Error(data.error);
    return data.enhanced_prompt ?? raw;
  }

  async function callGenerate(finalPrompt: string): Promise<string> {
    const res = await fetch(`${IMAGE_AGENT_URL}/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: finalPrompt }),
    });
    if (!res.ok) {
      const e = await res.json().catch(() => ({}));
      throw new Error(e?.detail ?? `Generate HTTP ${res.status}`);
    }
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    if (!data.image_base64) throw new Error("Empty image response");
    return data.image_base64;
  }

  // ── Submit handler ─────────────────────────────────────────────────────────
  async function handleSubmit(selectedMode: Mode) {
    if (!prompt.trim() || isLoading) return;
    reset();
    setMode(selectedMode);
    setError(null);

    try {
      let finalPrompt = prompt.trim();

      if (selectedMode === "enhance") {
        setStage("enhancing");
        finalPrompt = await callEnhance(prompt.trim());
        setEnhancedPrompt(finalPrompt);
      }

      setStage("generating");
      const b64 = await callGenerate(finalPrompt);
      setImageBase64(b64);
      setStage("done");

    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setStage("idle");
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <main className="page-wrapper">
      <div className="container">

        {/* Header */}
        <header className="header">
          <div className="header-logo">
            <div className="logo-icon" aria-hidden="true">✦</div>
            <span className="logo-text">EduVision</span>
          </div>
          <h1>Generate &amp; <span>Interact</span><br />with Educational AI</h1>
          <p className="header-subtitle">
            Enhance with Qwen 2.5-3B, generate with FLUX.1-dev, and tap any object to analyze with SAM 2 + Qwen2.5-VL.
          </p>

          {/* Agent health row */}
          <div style={{ display: "flex", gap: 10, justifyContent: "center", marginTop: 16, flexWrap: "wrap" }}>
            <HealthPill label="Prompt Agent" status={promptHealth} />
            <HealthPill label="Image Agent" status={imageHealth} />
            <HealthPill label="Interactive Agent" status={interactiveHealth} />
          </div>
        </header>

        {/* Prompt input */}
        <div className="glass-card prompt-form">
          <label htmlFor="prompt-input" className="prompt-label">Your Prompt</label>
          <textarea
            id="prompt-input"
            className="prompt-textarea"
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
            placeholder="e.g. photosynthesis diagram for 8th graders with labeled chloroplasts"
            rows={4}
            disabled={isLoading}
          />

          <div className="prompt-actions" style={{ marginTop: 16 }}>
            <p className="prompt-hint">Direct skips enhancement · Enhance uses Qwen 2.5-3B</p>
            <div style={{ display: "flex", gap: 10 }}>
              {/* Direct Submit */}
              <button
                id="direct-btn"
                type="button"
                className="btn-secondary"
                onClick={() => handleSubmit("direct")}
                disabled={isLoading || !prompt.trim()}
              >
                {mode === "direct" && isLoading
                  ? <><span className="btn-spinner" />Generating…</>
                  : <>⚡ Direct</>
                }
              </button>

              {/* Enhance & Generate */}
              <button
                id="enhance-btn"
                type="button"
                className="btn-generate"
                onClick={() => handleSubmit("enhance")}
                disabled={isLoading || !prompt.trim()}
              >
                {mode === "enhance" && stage === "enhancing"
                  ? <><span className="btn-spinner" />Enhancing…</>
                  : mode === "enhance" && stage === "generating"
                  ? <><span className="btn-spinner" />Generating…</>
                  : <>✦ Enhance &amp; Generate</>
                }
              </button>
            </div>
          </div>
        </div>

        {/* Stage indicator */}
        {isLoading && (
          <div className="glass-card loading-card" aria-live="polite">
            <div className="spinner" />
            <p className="loading-stage">
              {stage === "enhancing"
                ? "✦ Enhancing with Qwen 2.5-3B…"
                : "🎨 Generating with FLUX.1-dev (A10G) — ~30-60s…"}
            </p>
            {mode === "enhance" && (
              <div className="loading-stages">
                <span className={`stage-pill ${stage === "enhancing" ? "active" : "done"}`}>
                  {stage !== "enhancing" ? "✓ " : ""}Enhance
                </span>
                <span className={`stage-pill ${stage === "generating" ? "active" : ""}`}>
                  Generate
                </span>
              </div>
            )}
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="error-banner" role="alert">
            <strong>Failed</strong>{error}
          </div>
        )}

        {/* Enhanced prompt pill */}
        {enhancedPrompt && stage !== "enhancing" && (
          <div className="glass-card enhanced-prompt-card" aria-live="polite">
            <div className="enhanced-prompt-header">
              <span className="enhanced-badge">✦ Enhanced Prompt</span>
              <span className="enhanced-model-tag">Qwen 2.5-3B · SKILL.md</span>
            </div>
            <p id="enhanced-prompt-text" className="enhanced-prompt-text">
              &ldquo;{enhancedPrompt}&rdquo;
            </p>
          </div>
        )}

        {/* Generated Image Result & Interactive Section */}
        {imageBase64 && stage === "done" && (
          <div style={{ marginTop: 24 }}>
            <div className="section-title">
              <h2>Interactive Image Analysis</h2>
              <p>Tap any object or drag a box to segment with SAM 2 and explain with Qwen2.5-VL</p>
            </div>

            <InteractiveCanvas imageBase64={imageBase64} />
          </div>
        )}

        {/* Reset */}
        {stage === "done" && (
          <div style={{ textAlign: "center", marginTop: 28 }}>
            <button id="reset-btn" type="button" className="btn-ghost" onClick={reset}>
              ← New prompt
            </button>
          </div>
        )}

      </div>
    </main>
  );
}

// ── Health pill sub-component ──────────────────────────────────────────────────

function HealthPill({ label, status }: { label: string; status: "ok"|"error"|"checking" }) {
  return (
    <div className="health-row">
      <span className={`health-dot ${
        status === "ok" ? "health-ok" : status === "error" ? "health-error" : "health-checking"
      }`} />
      <span className="health-label">{label}</span>
      <span className="health-label" style={{ opacity: 0.5 }}>
        {status === "ok" ? "online" : status === "error" ? "offline" : "…"}
      </span>
    </div>
  );
}
