"use client";

import { useState } from "react";
import { Check, Copy, FileText } from "lucide-react";

interface Props {
  text: string;
}

export default function OcrResult({ text }: Props) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isEmpty = !text.trim();
  const wordCount = text.split(/\s+/).filter(Boolean).length;

  return (
    <section
      aria-label="Extracted text result"
      style={{
        borderRadius: "1.5rem",
        border: "1px solid rgba(255,255,255,0.08)",
        background: "rgba(255,255,255,0.03)",
        backdropFilter: "blur(12px)",
        WebkitBackdropFilter: "blur(12px)",
        padding: "1.5rem",
      }}
    >
      {/* Header row */}
      <div
        style={{
          marginBottom: "1rem",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <FileText
            className="h-4 w-4"
            style={{ color: "#a78bfa" }}
            strokeWidth={1.75}
          />
          <h3
            style={{
              fontSize: "0.875rem",
              fontWeight: 600,
              color: "rgba(255,255,255,0.9)",
            }}
          >
            Extracted Sinhala Text
          </h3>
          {!isEmpty && (
            <span
              style={{
                borderRadius: "9999px",
                background: "rgba(139,92,246,0.15)",
                padding: "0.125rem 0.625rem",
                fontSize: "0.75rem",
                color: "#c4b5fd",
              }}
            >
              {wordCount} {wordCount === 1 ? "word" : "words"}
            </span>
          )}
        </div>

        {!isEmpty && (
          <button
            id="btn-copy-text"
            onClick={handleCopy}
            aria-label="Copy extracted text to clipboard"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.375rem",
              borderRadius: "0.5rem",
              background: "rgba(255,255,255,0.08)",
              border: "none",
              padding: "0.375rem 0.75rem",
              fontSize: "0.75rem",
              fontWeight: 500,
              color: copied ? "#34d399" : "rgba(255,255,255,0.6)",
              cursor: "pointer",
              transition: "background 150ms ease, color 150ms ease",
            }}
            onMouseEnter={(e) =>
              (e.currentTarget.style.background = "rgba(255,255,255,0.13)")
            }
            onMouseLeave={(e) =>
              (e.currentTarget.style.background = "rgba(255,255,255,0.08)")
            }
          >
            {copied ? (
              <>
                <Check className="h-3.5 w-3.5" strokeWidth={2} />
                <span>Copied</span>
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5" strokeWidth={1.75} />
                <span>Copy</span>
              </>
            )}
          </button>
        )}
      </div>

      {/* Text body */}
      {isEmpty ? (
        <p
          style={{
            padding: "2rem 0",
            textAlign: "center",
            fontSize: "0.875rem",
            color: "rgba(255,255,255,0.25)",
          }}
        >
          No text detected in the image
        </p>
      ) : (
        <div style={{ position: "relative" }}>
          <pre
            id="ocr-output-text"
            className="sinhala-text"
            style={{
              maxHeight: "18rem",
              overflowY: "auto",
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              borderRadius: "0.75rem",
              background: "rgba(0,0,0,0.35)",
              padding: "1rem 1.25rem",
              fontSize: "1rem",
              lineHeight: 1.9,
              color: "rgba(255,255,255,0.85)",
            }}
          >
            {text}
          </pre>
        </div>
      )}
    </section>
  );
}
