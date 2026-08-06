"use client";

import { useState } from "react";
import { ArrowRight, RefreshCw, Sparkles, Zap } from "lucide-react";
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
      await new Promise((r) => setTimeout(r, 400)); // brief pause for UX
      setStep("enhancing");
      // Simulate enhancing state — real latency is in processImage call
      const res = await processImage(file);
      setStep("extracting");
      await new Promise((r) => setTimeout(r, 300)); // show extracting state briefly
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

  const isProcessing = step === "uploading" || step === "enhancing" || step === "extracting";

  return (
    <main className="min-h-screen bg-[#0a0a0f] text-white">
      {/* Background gradient orbs */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -top-40 -left-40 h-96 w-96 rounded-full bg-violet-600/20 blur-3xl" />
        <div className="absolute top-1/2 right-0 h-80 w-80 rounded-full bg-indigo-600/15 blur-3xl" />
        <div className="absolute bottom-0 left-1/3 h-72 w-72 rounded-full bg-purple-600/10 blur-3xl" />
      </div>

      <div className="relative z-10 mx-auto max-w-4xl px-4 py-16">
        {/* Header */}
        <div className="mb-14 text-center">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-violet-500/30 bg-violet-500/10 px-4 py-1.5 text-sm text-violet-300">
            <Zap className="h-3.5 w-3.5" />
            SRCNN + TrOCR · Modal Serverless
          </div>
          <h1 className="mt-4 text-5xl font-bold tracking-tight">
            Image{" "}
            <span className="bg-gradient-to-r from-violet-400 to-indigo-400 bg-clip-text text-transparent">
              Enhancement
            </span>{" "}
            &amp; OCR
          </h1>
          <p className="mt-4 text-lg text-white/50">
            Upload a low-quality image. AI enhances it 4× with SRCNN, then
            extracts text using TrOCR.
          </p>
        </div>

        {/* Upload + action */}
        <div className="mb-8 rounded-3xl border border-white/10 bg-white/[0.03] p-6 backdrop-blur-sm">
          <ImageUploader onFileSelected={handleFileSelected} disabled={isProcessing} />

          <div className="mt-5 flex items-center justify-between">
            <p className="text-sm text-white/40">
              {file ? `Selected: ${file.name}` : "No image selected"}
            </p>

            <div className="flex gap-3">
              {result && (
                <button
                  onClick={handleReset}
                  className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-white/70 transition-all hover:bg-white/10"
                >
                  <RefreshCw className="h-4 w-4" />
                  Reset
                </button>
              )}

              <button
                onClick={handleProcess}
                disabled={!file || isProcessing}
                className={`
                  flex items-center gap-2 rounded-xl px-6 py-2.5 text-sm font-semibold
                  transition-all duration-300
                  ${!file || isProcessing
                    ? "cursor-not-allowed bg-violet-500/20 text-violet-400/40"
                    : "bg-gradient-to-r from-violet-600 to-indigo-600 text-white shadow-lg shadow-violet-500/25 hover:from-violet-500 hover:to-indigo-500 hover:shadow-violet-500/40 active:scale-[0.98]"
                  }
                `}
              >
                <Sparkles className="h-4 w-4" />
                {isProcessing ? "Processing…" : "Enhance & Extract"}
                {!isProcessing && <ArrowRight className="h-4 w-4" />}
              </button>
            </div>
          </div>
        </div>

        {/* Processing status */}
        {step !== "idle" && (
          <div className="mb-8">
            <ProcessingStatus step={step} errorMessage={errorMsg} />
          </div>
        )}

        {/* Results */}
        {result && (
          <div className="flex flex-col gap-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Before / After comparison */}
            <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-6 backdrop-blur-sm">
              <h2 className="mb-6 flex items-center gap-2 text-lg font-semibold text-white">
                <Sparkles className="h-5 w-5 text-violet-400" />
                Enhancement Result
              </h2>
              <ImageComparison
                originalB64={result.original_b64}
                enhancedB64={result.enhanced_b64}
              />
            </div>

            {/* OCR text */}
            <OcrResult text={result.extracted_text} />
          </div>
        )}
      </div>
    </main>
  );
}
