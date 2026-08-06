"use client";

import { useCallback, useRef, useState } from "react";
import { Upload, Image as ImageIcon } from "lucide-react";

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

  return (
    <div
      onClick={() => !disabled && inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDrop}
      className={`
        relative flex flex-col items-center justify-center
        min-h-64 rounded-2xl border-2 border-dashed
        transition-all duration-300 cursor-pointer select-none
        ${dragOver
          ? "border-violet-400 bg-violet-500/10 scale-[1.01]"
          : "border-white/20 bg-white/5 hover:border-violet-400/60 hover:bg-violet-500/5"
        }
        ${disabled ? "pointer-events-none opacity-50" : ""}
      `}
    >
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED.join(",")}
        className="hidden"
        onChange={onInputChange}
        disabled={disabled}
      />

      {preview ? (
        <div className="w-full p-4">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={preview}
            alt="Selected"
            className="mx-auto max-h-56 rounded-xl object-contain shadow-lg"
          />
          <p className="mt-3 text-center text-sm text-white/50">
            Click or drop to replace
          </p>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-4 p-8 text-center">
          <div className="rounded-full bg-violet-500/20 p-5">
            {dragOver ? (
              <ImageIcon className="h-8 w-8 text-violet-300" />
            ) : (
              <Upload className="h-8 w-8 text-violet-400" />
            )}
          </div>
          <div>
            <p className="text-base font-medium text-white">
              Drop your image here
            </p>
            <p className="mt-1 text-sm text-white/50">
              or click to browse &mdash; JPG, PNG, WEBP, BMP
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
