// frontend/app/page.tsx
// Full workflow: Enhance (Qwen 2.5-3B) → Generate (FLUX.1-dev) → Interactive (SAM 2 + Qwen2.5-VL)

"use client";

import React, { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import InteractiveCanvas from "@/components/InteractiveCanvas";

// ThreeDViewer uses Three.js (WebGL) — must be loaded client-side only
const ThreeDViewer = dynamic(() => import("@/components/ThreeDViewer"), { ssr: false });

const PROMPT_AGENT_URL =
  process.env.NEXT_PUBLIC_PROMPT_AGENT_URL ??
  "https://kojithan-y--prompt-agent-api-dev.modal.run";

const IMAGE_AGENT_URL =
  process.env.NEXT_PUBLIC_IMAGE_AGENT_URL ??
  "https://kojithan-y--image-agent-api-dev.modal.run";

const INTERACTIVE_AGENT_URL =
  process.env.NEXT_PUBLIC_INTERACTIVE_AGENT_URL ??
  "https://kojithan-y--interactive-agent-api-dev.modal.run";

const THREED_AGENT_URL =
  process.env.NEXT_PUBLIC_THREED_AGENT_URL ??
  "https://kojithan-y--threed-agent-api-dev.modal.run";

// ── Types ──────────────────────────────────────────────────────────────────────

type Stage      = "idle" | "enhancing" | "generating" | "done";
type Mode       = "direct" | "enhance";
type SpeedMode  = "normal" | "pro" | "promax";
type ThreeDStage = "idle" | "converting" | "done";

// ── Speed mode config ──────────────────────────────────────────────────────────

const SPEED_MODES: {
  id: SpeedMode;
  label: string;
  icon: string;
  desc: string;
  promptGpu: string;
  imageGpu: string;
  interactiveGpu: string;
}[] = [
  {
    id: "normal",
    label: "Normal",
    icon: "⚡",
    desc: "T4 · A10G · A10G",
    promptGpu: "T4",
    imageGpu: "A10G",
    interactiveGpu: "A10G",
  },
  {
    id: "pro",
    label: "Pro",
    icon: "🚀",
    desc: "A10G · A100 · A100",
    promptGpu: "A10G",
    imageGpu: "A100",
    interactiveGpu: "A100",
  },
  {
    id: "promax",
    label: "Pro Max",
    icon: "⚡⚡",
    desc: "A10G · H100 · H100",
    promptGpu: "A10G",
    imageGpu: "H100",
    interactiveGpu: "H100",
  },
];

// ── Component ──────────────────────────────────────────────────────────────────

export default function HomePage() {
  const [prompt, setPrompt]               = useState("");
  const [stage, setStage]                 = useState<Stage>("idle");
  const [mode, setMode]                   = useState<Mode>("enhance");
  const [speedMode, setSpeedMode]         = useState<SpeedMode>("pro");
  const [enhancedPrompt, setEnhancedPrompt] = useState<string | null>(null);
  const [imageBase64, setImageBase64]     = useState<string | null>(null);
  const [error, setError]                 = useState<string | null>(null);

  // 3D conversion state
  const [threedStage, setThreedStage]   = useState<ThreeDStage>("idle");
  const [glbBase64, setGlbBase64]       = useState<string | null>(null);
  const [glbSizeKb, setGlbSizeKb]       = useState<number | undefined>(undefined);
  const [threedError, setThreedError]   = useState<string | null>(null);

  const [promptHealth, setPromptHealth]           = useState<"ok"|"error"|"checking">("checking");
  const [imageHealth, setImageHealth]             = useState<"ok"|"error"|"checking">("checking");
  const [interactiveHealth, setInteractiveHealth] = useState<"ok"|"error"|"checking">("checking");
  const [threedHealth, setThreedHealth]           = useState<"ok"|"error"|"checking">("checking");

  const isLoading = stage === "enhancing" || stage === "generating";
  const currentSpeedCfg = SPEED_MODES.find(s => s.id === speedMode)!;

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

    fetch(`${THREED_AGENT_URL}/health`)
      .then(r => r.ok ? setThreedHealth("ok") : setThreedHealth("error"))
      .catch(() => setThreedHealth("error"));
  }, []);

  // ── Helpers ────────────────────────────────────────────────────────────────
  function reset() {
    setStage("idle");
    setEnhancedPrompt(null);
    setImageBase64(null);
    setError(null);
    setThreedStage("idle");
    setGlbBase64(null);
    setGlbSizeKb(undefined);
    setThreedError(null);
  }

  async function callEnhance(raw: string): Promise<string> {
    const res = await fetch(`${PROMPT_AGENT_URL}/enhance`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ raw_prompt: raw, speed_mode: speedMode }),
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
      body: JSON.stringify({ prompt: finalPrompt, speed_mode: speedMode }),
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

  // ── 3D Conversion handler ──────────────────────────────────────────────────
  async function handleConvertTo3D() {
    if (!imageBase64 || threedStage === "converting") return;
    setThreedStage("converting");
    setThreedError(null);
    setGlbBase64(null);

    try {
      const res = await fetch(`${THREED_AGENT_URL}/convert`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image_base64: imageBase64,
          speed_mode: speedMode,
          texture: true,
          num_inference_steps: speedMode === "promax" ? 50 : 30,
        }),
      });
      if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        throw new Error(e?.detail ?? `3D Convert HTTP ${res.status}`);
      }
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      if (!data.glb_base64) throw new Error("Empty GLB response");
      setGlbBase64(data.glb_base64);
      setGlbSizeKb(data.size_kb);
      setThreedStage("done");
    } catch (err: unknown) {
      setThreedError(err instanceof Error ? err.message : "3D conversion failed");
      setThreedStage("idle");
    }
  }

  // ── Loading label ──────────────────────────────────────────────────────────
  function loadingLabel(): string {
    if (stage === "enhancing") {
      return `✦ Enhancing with Qwen 2.5-3B on ${currentSpeedCfg.promptGpu}…`;
    }
    return `🎨 Generating with FLUX.1-dev on ${currentSpeedCfg.imageGpu}…`;
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
            <HealthPill label="3D Agent" status={threedHealth} />
          </div>
        </header>

        {/* Speed Mode Selector */}
        <div className="speed-mode-section">
          <p className="speed-mode-label">Speed Mode</p>
          <div className="speed-mode-picker">
            {SPEED_MODES.map(sm => (
              <button
                key={sm.id}
                id={`speed-${sm.id}`}
                type="button"
                className={`speed-pill speed-pill-${sm.id} ${speedMode === sm.id ? "active" : ""}`}
                onClick={() => !isLoading && setSpeedMode(sm.id)}
                disabled={isLoading}
                aria-pressed={speedMode === sm.id}
              >
                <span className="speed-pill-icon">{sm.icon}</span>
                <span className="speed-pill-name">{sm.label}</span>
                <span className="speed-pill-gpus">{sm.desc}</span>
              </button>
            ))}
          </div>
          <p className="speed-mode-hint">
            {speedMode === "normal" && "Standard GPUs — same quality, moderate wait times."}
            {speedMode === "pro" && "Upgraded GPUs — faster enhancement & interactive analysis."}
            {speedMode === "promax" && "Top-tier GPUs — maximum speed across all stages."}
          </p>
        </div>

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
            <p className="loading-stage">{loadingLabel()}</p>
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
            {/* GPU badge during loading */}
            <div className="loading-gpu-badge">
              <span className={`speed-badge-inline speed-badge-${speedMode}`}>
                {currentSpeedCfg.icon} {currentSpeedCfg.label}
              </span>
              <span className="loading-gpu-text">
                {stage === "enhancing"
                  ? `GPU: ${currentSpeedCfg.promptGpu}`
                  : `GPU: ${currentSpeedCfg.imageGpu}`}
              </span>
            </div>
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
              <span className="enhanced-model-tag">Qwen 2.5-3B · {currentSpeedCfg.promptGpu}</span>
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

            <InteractiveCanvas imageBase64={imageBase64} speedMode={speedMode} />

            {/* ── Convert to 3D section ──────────────────────────────────── */}
            <div className="threed-section">
              <div className="section-title" style={{ marginTop: 32 }}>
                <h2>🧊 2D → 3D Conversion</h2>
                <p>Convert your generated image into a textured 3D model using Hunyuan3D-2</p>
              </div>

              {threedStage === "idle" && (
                <div style={{ textAlign: "center", marginTop: 16 }}>
                  <button
                    id="convert-3d-btn"
                    type="button"
                    className="btn-threed"
                    onClick={handleConvertTo3D}
                  >
                    🧊 Convert to 3D
                    <span className="btn-threed-gpu">
                      {speedMode === "promax" ? "H100" : "A10G"}
                    </span>
                  </button>
                  <p className="speed-mode-hint" style={{ marginTop: 8 }}>
                    {speedMode === "promax"
                      ? "Pro Max · H100 · ~2-3 min (shape + texture)"
                      : "A10G · ~3-5 min (shape + texture)"}
                  </p>
                </div>
              )}

              {threedStage === "converting" && (
                <div className="glass-card loading-card" aria-live="polite" style={{ marginTop: 16 }}>
                  <div className="spinner" />
                  <p className="loading-stage">🧊 Hunyuan3D-2 — generating shape &amp; texture…</p>
                  <div className="loading-stages">
                    <span className="stage-pill active">Shape Generation</span>
                    <span className="stage-pill">Texture Synthesis</span>
                    <span className="stage-pill">GLB Export</span>
                  </div>
                  <div className="loading-gpu-badge">
                    <span className={`speed-badge-inline speed-badge-${speedMode}`}>
                      {currentSpeedCfg.icon} {currentSpeedCfg.label}
                    </span>
                    <span className="loading-gpu-text">
                      GPU: {speedMode === "promax" ? "H100" : "A10G"}
                    </span>
                  </div>
                </div>
              )}

              {threedError && (
                <div className="error-banner" role="alert" style={{ marginTop: 16 }}>
                  <strong>3D conversion failed</strong>{threedError}
                </div>
              )}

              {threedStage === "done" && glbBase64 && (
                <ThreeDViewer glbBase64={glbBase64} sizeKb={glbSizeKb} />
              )}

              {threedStage === "done" && (
                <div style={{ textAlign: "center", marginTop: 12 }}>
                  <button
                    type="button"
                    className="btn-ghost"
                    onClick={() => { setThreedStage("idle"); setGlbBase64(null); setThreedError(null); }}
                  >
                    ↺ Convert again
                  </button>
                </div>
              )}
            </div>
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
