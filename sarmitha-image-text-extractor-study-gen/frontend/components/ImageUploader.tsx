"use client";

import { useCallback, useRef, useState } from "react";
import { Upload, ImageIcon } from "lucide-react";

interface Props {
  onFileSelected: (file: File) => void;
  disabled?: boolean;
}

const ACCEPTED = ["image/jpeg", "image/png", "image/webp", "image/bmp"];

export default function ImageUploader({ onFileSelected, disabled }: Props) {
  const [dragOver, setDragOver] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    (file: File) => {
      if (!ACCEPTED.includes(file.type)) return;
      const url = URL.createObjectURL(file);
      setPreview(url);
      onFileSelected(file);
    },
    [onFileSelected]
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  const borderColor = dragOver
    ? "rgba(139,92,246,0.7)"
    : "rgba(255,255,255,0.12)";

  const bgColor = dragOver
    ? "rgba(139,92,246,0.08)"
    : "rgba(255,255,255,0.03)";

  return (
    <div
      id="image-drop-zone"
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-label="Upload image by clicking or dragging"
      onClick={() => !disabled && inputRef.current?.click()}
      onKeyDown={(e) => {
        if ((e.key === "Enter" || e.key === " ") && !disabled) {
          inputRef.current?.click();
        }
      }}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDrop}
      style={{
        position: "relative",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "16rem",
        borderRadius: "1rem",
        border: `2px dashed ${borderColor}`,
        background: bgColor,
        transition: "border-color 200ms ease, background 200ms ease",
        cursor: disabled ? "default" : "pointer",
        userSelect: "none",
        opacity: disabled ? 0.5 : 1,
        pointerEvents: disabled ? "none" : "auto",
      }}
    >
      <input
        ref={inputRef}
        id="image-file-input"
        type="file"
        accept={ACCEPTED.join(",")}
        style={{ display: "none" }}
        onChange={onInputChange}
        disabled={disabled}
        aria-label="Image file input"
      />

      {preview ? (
        <div style={{ width: "100%", padding: "1rem" }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={preview}
            alt="Selected image preview"
            style={{
              display: "block",
              margin: "0 auto",
              maxHeight: "14rem",
              borderRadius: "0.75rem",
              objectFit: "contain",
              boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
            }}
          />
          <p
            style={{
              marginTop: "0.75rem",
              textAlign: "center",
              fontSize: "0.8125rem",
              color: "rgba(255,255,255,0.4)",
            }}
          >
            Click or drop to replace
          </p>
        </div>
      ) : (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "1rem",
            padding: "2rem",
            textAlign: "center",
          }}
        >
          <div
            style={{
              borderRadius: "9999px",
              background: "rgba(139,92,246,0.15)",
              padding: "1.25rem",
              transition: "background 200ms ease",
            }}
          >
            {dragOver ? (
              <ImageIcon
                className="h-8 w-8"
                style={{ color: "#c4b5fd" }}
                strokeWidth={1.5}
              />
            ) : (
              <Upload
                className="h-8 w-8"
                style={{ color: "#a78bfa" }}
                strokeWidth={1.5}
              />
            )}
          </div>
          <div>
            <p
              style={{
                fontSize: "0.9375rem",
                fontWeight: 500,
                color: "rgba(255,255,255,0.85)",
              }}
            >
              Drop your Sinhala handwritten image here
            </p>
            <p
              style={{
                marginTop: "0.25rem",
                fontSize: "0.8125rem",
                color: "rgba(255,255,255,0.4)",
              }}
            >
              or click to browse &mdash; JPG, PNG, WEBP, BMP
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
