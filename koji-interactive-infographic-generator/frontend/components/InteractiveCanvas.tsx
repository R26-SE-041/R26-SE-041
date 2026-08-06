// frontend/components/InteractiveCanvas.tsx
// Interactive Canvas for generated image segmentation & Qwen2.5-VL visual analysis

"use client";

import React, { useState, useRef, useEffect, MouseEvent } from "react";

const INTERACTIVE_AGENT_URL =
  process.env.NEXT_PUBLIC_INTERACTIVE_AGENT_URL ??
  "https://kojithan-y--interactive-agent-api-dev.modal.run";

type SelectionType = "point" | "box";
type AnalysisMode = "identify" | "explain" | "ask";

interface InteractionCoords {
  type: SelectionType;
  coords: number[]; // [x, y] or [x1, y1, x2, y2] normalized 0..1
}

type SpeedMode = "normal" | "pro" | "promax";

interface InteractiveCanvasProps {
  imageBase64: string; // Base64 PNG
  speedMode?: SpeedMode;
}

export default function InteractiveCanvas({ imageBase64, speedMode = "pro" }: InteractiveCanvasProps) {
  const [selectionType, setSelectionType] = useState<SelectionType>("point");
  const [analysisMode, setAnalysisMode] = useState<AnalysisMode>("identify");
  const [customQuestion, setCustomQuestion] = useState("");

  const [currentSelection, setCurrentSelection] = useState<InteractionCoords | null>(null);
  const [isDrawingBox, setIsDrawingBox] = useState(false);
  const [boxStart, setBoxStart] = useState<{ x: number; y: number } | null>(null);
  const [boxCurrent, setBoxCurrent] = useState<{ x: number; y: number } | null>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [highlightedImage, setHighlightedImage] = useState<string | null>(null);
  const [analysisResult, setAnalysisResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);

  // Clear analysis when selection mode changes
  const handleTypeChange = (type: SelectionType) => {
    setSelectionType(type);
    setCurrentSelection(null);
    setBoxStart(null);
    setBoxCurrent(null);
    setHighlightedImage(null);
    setAnalysisResult(null);
    setError(null);
  };

  // Helper to calculate normalized coords (0..1) relative to image
  const getNormalizedCoords = (e: MouseEvent<HTMLDivElement>) => {
    if (!imageRef.current) return { x: 0, y: 0 };
    const rect = imageRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const y = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));
    return { x, y };
  };

  const handleMouseDown = (e: MouseEvent<HTMLDivElement>) => {
    if (isLoading) return;
    const { x, y } = getNormalizedCoords(e);

    if (selectionType === "point") {
      setCurrentSelection({ type: "point", coords: [x, y] });
    } else {
      setIsDrawingBox(true);
      setBoxStart({ x, y });
      setBoxCurrent({ x, y });
    }
  };

  const handleMouseMove = (e: MouseEvent<HTMLDivElement>) => {
    if (!isDrawingBox || selectionType !== "box") return;
    const { x, y } = getNormalizedCoords(e);
    setBoxCurrent({ x, y });
  };

  const handleMouseUp = () => {
    if (!isDrawingBox || !boxStart || !boxCurrent) return;
    setIsDrawingBox(false);

    const x1 = Math.min(boxStart.x, boxCurrent.x);
    const y1 = Math.min(boxStart.y, boxCurrent.y);
    const x2 = Math.max(boxStart.x, boxCurrent.x);
    const y2 = Math.max(boxStart.y, boxCurrent.y);

    // If tiny click without dragging, default to a box centered around click point
    if (Math.abs(x2 - x1) < 0.02 || Math.abs(y2 - y1) < 0.02) {
      const cx = boxStart.x;
      const cy = boxStart.y;
      const margin = 0.08;
      const px1 = Math.max(0, cx - margin);
      const py1 = Math.max(0, cy - margin);
      const px2 = Math.min(1, cx + margin);
      const py2 = Math.min(1, cy + margin);
      setCurrentSelection({ type: "box", coords: [px1, py1, px2, py2] });
      return;
    }

    setCurrentSelection({ type: "box", coords: [x1, y1, x2, y2] });
  };

  // Run analysis API request
  const runAnalysis = async () => {
    if (!currentSelection || isLoading) return;

    setIsLoading(true);
    setError(null);
    setAnalysisResult(null);

    try {
      const res = await fetch(`${INTERACTIVE_AGENT_URL}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image_base64: imageBase64,
          interaction: currentSelection,
          mode: analysisMode,
          question: analysisMode === "ask" ? customQuestion.trim() : undefined,
          speed_mode: speedMode,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData?.detail?.error ?? errData?.detail ?? `HTTP ${res.status}`);
      }

      const data = await res.json();
      if (data.error) throw new Error(data.error);

      if (data.highlighted_base64) {
        setHighlightedImage(`data:image/png;base64,${data.highlighted_base64}`);
      }
      setAnalysisResult(data.response_text || "No analysis provided.");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="interactive-container">
      {/* Control Toolbar */}
      <div className="interactive-toolbar">
        <div className="toolbar-group">
          <span className="toolbar-label">Interaction Mode:</span>
          <button
            type="button"
            className={`toolbar-btn ${selectionType === "point" ? "active" : ""}`}
            onClick={() => handleTypeChange("point")}
          >
            🎯 Tap Object
          </button>
          <button
            type="button"
            className={`toolbar-btn ${selectionType === "box" ? "active" : ""}`}
            onClick={() => handleTypeChange("box")}
          >
            🔲 Circle / Box Region
          </button>
        </div>

        <span className="toolbar-hint">
          {selectionType === "point"
            ? "Click any object in the diagram to segment & analyze"
            : "Click and drag a box around a region"}
        </span>
      </div>

      {/* Interactive Image Container */}
      <div
        ref={containerRef}
        className="canvas-wrap"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
      >
        {/* Base / Highlighted Image */}
        <img
          ref={imageRef}
          src={highlightedImage || `data:image/png;base64,${imageBase64}`}
          alt="Interactive Educational Image"
          className="interactive-image"
          draggable={false}
        />

        {/* Selection Indicator Overlays */}
        {selectionType === "point" && currentSelection && (
          <div
            className="point-marker"
            style={{
              left: `${currentSelection.coords[0] * 100}%`,
              top: `${currentSelection.coords[1] * 100}%`,
            }}
          />
        )}

        {/* Box Drawing Preview */}
        {isDrawingBox && boxStart && boxCurrent && (
          <div
            className="box-marker drawing"
            style={{
              left: `${Math.min(boxStart.x, boxCurrent.x) * 100}%`,
              top: `${Math.min(boxStart.y, boxCurrent.y) * 100}%`,
              width: `${Math.abs(boxCurrent.x - boxStart.x) * 100}%`,
              height: `${Math.abs(boxCurrent.y - boxStart.y) * 100}%`,
            }}
          />
        )}

        {/* Completed Box Selection */}
        {selectionType === "box" && currentSelection && !isDrawingBox && (
          <div
            className="box-marker"
            style={{
              left: `${currentSelection.coords[0] * 100}%`,
              top: `${currentSelection.coords[1] * 100}%`,
              width: `${(currentSelection.coords[2] - currentSelection.coords[0]) * 100}%`,
              height: `${(currentSelection.coords[3] - currentSelection.coords[1]) * 100}%`,
            }}
          />
        )}
      </div>

      {/* Action Options (shown after selection) */}
      {currentSelection && (
        <div className="glass-card action-panel">
          <div className="action-mode-selector">
            <button
              type="button"
              className={`mode-btn ${analysisMode === "identify" ? "active" : ""}`}
              onClick={() => setAnalysisMode("identify")}
            >
              🏷️ Identify Object
            </button>
            <button
              type="button"
              className={`mode-btn ${analysisMode === "explain" ? "active" : ""}`}
              onClick={() => setAnalysisMode("explain")}
            >
              📖 Explain Region
            </button>
            <button
              type="button"
              className={`mode-btn ${analysisMode === "ask" ? "active" : ""}`}
              onClick={() => setAnalysisMode("ask")}
            >
              ❓ Ask Question
            </button>
          </div>

          {analysisMode === "ask" && (
            <div className="ask-input-wrap">
              <input
                type="text"
                className="ask-input"
                value={customQuestion}
                onChange={(e) => setCustomQuestion(e.target.value)}
                placeholder="e.g. What is the role of this organelle in cellular respiration?"
                onKeyDown={(e) => e.key === "Enter" && runAnalysis()}
              />
            </div>
          )}

          <div className="action-footer">
            <button
              type="button"
              className="btn-generate"
              onClick={runAnalysis}
              disabled={isLoading || (analysisMode === "ask" && !customQuestion.trim())}
            >
              {isLoading ? (
                <>
                  <span className="btn-spinner" />
                  SAM 2 &amp; Qwen2.5-VL analyzing…
                </>
              ) : (
                <>✦ Analyze Selected Region</>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Error display */}
      {error && (
        <div className="error-banner" style={{ marginTop: 16 }}>
          <strong>Interactive analysis failed</strong>
          {error}
        </div>
      )}

      {/* Result Display */}
      {analysisResult && (
        <div className="glass-card result-panel">
          <div className="result-header">
            <span className="enhanced-badge">✦ Qwen2.5-VL Visual Explanation</span>
            <span className="enhanced-model-tag">
              SAM 2 + Qwen2.5-VL-7B &middot; {speedMode === "normal" ? "A10G" : speedMode === "promax" ? "H100" : "A100"}
            </span>
          </div>
          <p className="result-text">{analysisResult}</p>
        </div>
      )}
    </div>
  );
}
