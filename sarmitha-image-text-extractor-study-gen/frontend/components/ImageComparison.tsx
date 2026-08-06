"use client";

import { useRef, useState } from "react";

interface Props {
  originalB64: string;
  enhancedB64: string;
}

export default function ImageComparison({ originalB64, enhancedB64 }: Props) {
  const [sliderX, setSliderX] = useState(50); // percent
  const containerRef = useRef<HTMLDivElement>(null);

  const updateSlider = (clientX: number) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const pct = Math.min(100, Math.max(0, ((clientX - rect.left) / rect.width) * 100));
    setSliderX(pct);
  };

  const onMouseMove = (e: React.MouseEvent) => {
    if (e.buttons !== 1) return;
    updateSlider(e.clientX);
  };

  const onTouchMove = (e: React.TouchEvent) => {
    updateSlider(e.touches[0].clientX);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-sm text-white/60">
        <span className="rounded-md bg-white/10 px-2 py-0.5 text-xs font-medium text-white/70">
          Original
        </span>
        <span className="text-xs text-white/40">← Drag slider →</span>
        <span className="rounded-md bg-violet-500/30 px-2 py-0.5 text-xs font-medium text-violet-300">
          Enhanced (4×)
        </span>
      </div>

      {/* Comparison container */}
      <div
        ref={containerRef}
        className="relative overflow-hidden rounded-xl select-none cursor-col-resize"
        style={{ aspectRatio: "16/9" }}
        onMouseMove={onMouseMove}
        onTouchMove={onTouchMove}
        onMouseDown={(e) => updateSlider(e.clientX)}
        onTouchStart={(e) => updateSlider(e.touches[0].clientX)}
      >
        {/* Enhanced image (full width base) */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={`data:image/png;base64,${enhancedB64}`}
          alt="Enhanced"
          className="absolute inset-0 h-full w-full object-contain"
          draggable={false}
        />

        {/* Original image clipped to left portion */}
        <div
          className="absolute inset-0 overflow-hidden"
          style={{ width: `${sliderX}%` }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={`data:image/png;base64,${originalB64}`}
            alt="Original"
            className="absolute inset-0 h-full object-contain"
            style={{ width: containerRef.current?.offsetWidth ?? 600 }}
            draggable={false}
          />
        </div>

        {/* Slider handle */}
        <div
          className="absolute inset-y-0 flex items-center justify-center"
          style={{ left: `${sliderX}%`, transform: "translateX(-50%)" }}
        >
          <div className="h-full w-0.5 bg-white/70" />
          <div className="absolute flex h-9 w-9 items-center justify-center rounded-full bg-white shadow-xl">
            <span className="text-[10px] font-bold text-gray-800 leading-none">⇔</span>
          </div>
        </div>
      </div>
    </div>
  );
}
