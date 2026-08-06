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

  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-sm">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-violet-400" />
          <h3 className="text-sm font-semibold text-white">Extracted Text</h3>
          {!isEmpty && (
            <span className="rounded-full bg-violet-500/20 px-2 py-0.5 text-xs text-violet-300">
              {text.split(/\s+/).filter(Boolean).length} words
            </span>
          )}
        </div>

        {!isEmpty && (
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 rounded-lg bg-white/10 px-3 py-1.5 text-xs font-medium text-white/70 transition-all hover:bg-white/15 hover:text-white"
          >
            {copied ? (
              <>
                <Check className="h-3.5 w-3.5 text-emerald-400" />
                <span className="text-emerald-400">Copied!</span>
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5" />
                Copy
              </>
            )}
          </button>
        )}
      </div>

      {isEmpty ? (
        <p className="py-8 text-center text-sm text-white/30">
          No text detected in the image
        </p>
      ) : (
        <div className="relative">
          <pre className="max-h-64 overflow-y-auto whitespace-pre-wrap rounded-xl bg-black/30 p-4 font-mono text-sm leading-relaxed text-white/80 scrollbar-thin scrollbar-thumb-white/10">
            {text}
          </pre>
        </div>
      )}
    </div>
  );
}
