"use client";

import { useState } from "react";
import {
  ArrowRight,
  RotateCcw,
  ScanText,
  ImageUp,
} from "lucide-react";
import ImageUploader from "@/components/ImageUploader";
import ImageComparison from "@/components/ImageComparison";
import OcrResult from "@/components/OcrResult";
import ProcessingStatus, { type Step } from "@/components/ProcessingStatus";
import { processImage, type ProcessResult, ApiError } from "@/lib/api";

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [step, setStep] = useState<Step>("idle");
  const [result, setResult] = useState<ProcessResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string>("");

  const handleFileSelected = (f: File) => {
    setFile(f);
    setResult(null);
    setStep("idle");
    setErrorMsg("");
  };

  const handleProcess = async () => {
    if (!file) return;
    setResult(null);
    setErrorMsg("");
    setStep("uploading");

    try {
      await new Promise((r) => setTimeout(r, 400));
      setStep("enhancing");
      const res = await processImage(file);
      setStep("extracting");
      await new Promise((r) => setTimeout(r, 300));
      setResult(res);
      setStep("done");
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? `[${err.status}] ${err.message}`
          : err instanceof Error
          ? err.message
          : "An unexpected error occurred";
      setErrorMsg(msg);
      setStep("error");
    }
  };

  const handleReset = () => {
    setFile(null);
    setResult(null);
    setStep("idle");
    setErrorMsg("");
  };

  const isProcessing =
    step === "uploading" || step === "enhancing" || step === "extracting";

  return (
    <main className="min-h-screen bg-[#09090f] text-white">
      {/* Background ambient gradients */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden" aria-hidden="true">
        <div
          style={{
            position: "absolute",
            top: "-10rem",
            left: "-10rem",
            width: "28rem",
            height: "28rem",
            borderRadius: "9999px",
            background: "radial-gradient(circle, rgba(124,58,237,0.18) 0%, transparent 70%)",
            filter: "blur(60px)",
          }}
        />
        <div
          style={{
            position: "absolute",
            top: "50%",
            right: "-4rem",
            width: "22rem",
            height: "22rem",
            borderRadius: "9999px",
            background: "radial-gradient(circle, rgba(79,70,229,0.14) 0%, transparent 70%)",
            filter: "blur(60px)",
          }}
        />
        <div
          style={{
            position: "absolute",
            bottom: "0",
            left: "33%",
            width: "18rem",
            height: "18rem",
            borderRadius: "9999px",
            background: "radial-gradient(circle, rgba(109,40,217,0.10) 0%, transparent 70%)",
            filter: "blur(60px)",
          }}
        />
      </div>

      <div className="relative z-10 mx-auto max-w-4xl px-4 py-16">
        {/* Header */}
        <header className="mb-14 text-center">
          <div
            className="mb-4 inline-flex items-center gap-2 rounded-full border px-4 py-1.5 text-sm"
            style={{
              borderColor: "rgba(139,92,246,0.3)",
              background: "rgba(139,92,246,0.08)",
              color: "#c4b5fd",
            }}
          >
            <ScanText className="h-3.5 w-3.5" strokeWidth={1.75} />
            <span>SRCNN + TrOCR &middot; Modal Serverless</span>
          </div>

          <h1
            className="mt-4 text-5xl font-bold tracking-tight"
            style={{ lineHeight: 1.15 }}
          >
            Sinhala Handwritten{" "}
            <span
              style={{
                background: "linear-gradient(135deg, #a78bfa 0%, #818cf8 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
              }}
            >
              OCR
            </span>
          </h1>

          <p
            className="mt-4 text-lg"
            style={{ color: "rgba(255,255,255,0.45)", maxWidth: "36rem", margin: "1rem auto 0" }}
          >
            Upload a low-quality Sinhala handwritten image. The system enhances
            it 4x with SRCNN, then extracts the Sinhala text using a fine-tuned
            TrOCR model.
          </p>
        </header>

        {/* Upload panel */}
        <section
          className="mb-8 card p-6"
          aria-label="Image upload"
        >
          <ImageUploader
            onFileSelected={handleFileSelected}
            disabled={isProcessing}
          />

          <div className="mt-5 flex items-center justify-between">
            <p className="text-sm" style={{ color: "rgba(255,255,255,0.35)" }}>
              {file ? `Selected: ${file.name}` : "No image selected"}
            </p>

            <div className="flex gap-3">
              {result && (
                <button
                  id="btn-reset"
                  onClick={handleReset}
                  className="flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition-all"
                  style={{
                    border: "1px solid rgba(255,255,255,0.1)",
                    background: "rgba(255,255,255,0.04)",
                    color: "rgba(255,255,255,0.6)",
                  }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.background = "rgba(255,255,255,0.08)")
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.background = "rgba(255,255,255,0.04)")
                  }
                >
                  <RotateCcw className="h-4 w-4" strokeWidth={1.75} />
                  Reset
                </button>
              )}

              <button
                id="btn-process"
                onClick={handleProcess}
                disabled={!file || isProcessing}
                className="flex items-center gap-2 rounded-xl px-6 py-2.5 text-sm font-semibold transition-all"
                style={
                  !file || isProcessing
                    ? {
                        background: "rgba(139,92,246,0.15)",
                        color: "rgba(167,139,250,0.35)",
                        cursor: "not-allowed",
                      }
                    : {
                        background:
                          "linear-gradient(135deg, #7c3aed 0%, #4f46e5 100%)",
                        color: "#ffffff",
                        boxShadow: "0 8px 32px rgba(124,58,237,0.3)",
                      }
                }
                onMouseEnter={(e) => {
                  if (file && !isProcessing) {
                    e.currentTarget.style.boxShadow =
                      "0 12px 40px rgba(124,58,237,0.45)";
                    e.currentTarget.style.transform = "translateY(-1px)";
                  }
                }}
                onMouseLeave={(e) => {
                  if (file && !isProcessing) {
                    e.currentTarget.style.boxShadow =
                      "0 8px 32px rgba(124,58,237,0.3)";
                    e.currentTarget.style.transform = "translateY(0)";
                  }
                }}
                onMouseDown={(e) => {
                  if (file && !isProcessing) {
                    e.currentTarget.style.transform = "scale(0.98)";
                  }
                }}
                onMouseUp={(e) => {
                  if (file && !isProcessing) {
                    e.currentTarget.style.transform = "translateY(-1px)";
                  }
                }}
              >
                <ImageUp className="h-4 w-4" strokeWidth={1.75} />
                {isProcessing ? "Processing..." : "Enhance and Extract"}
                {!isProcessing && (
                  <ArrowRight className="h-4 w-4" strokeWidth={1.75} />
                )}
              </button>
            </div>
          </div>
        </section>

        {/* Processing status */}
        {step !== "idle" && (
          <div className="mb-8 animate-fade">
            <ProcessingStatus step={step} errorMessage={errorMsg} />
          </div>
        )}

        {/* Results */}
        {result && (
          <div
            className="flex flex-col gap-8 animate-in"
            style={{ animationDelay: "100ms" }}
          >
            {/* Before / After comparison */}
            <section className="card p-6" aria-label="Image comparison">
              <h2
                className="mb-6 flex items-center gap-2 text-base font-semibold"
                style={{ color: "rgba(255,255,255,0.9)" }}
              >
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="#a78bfa"
                  strokeWidth="1.75"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
                Enhancement Result
              </h2>
              <ImageComparison
                originalB64={result.original_b64}
                enhancedB64={result.enhanced_b64}
              />
            </section>

            {/* OCR text */}
            <OcrResult text={result.extracted_text} />
          </div>
        )}
      </div>
    </main>
  );
}
