"use client";

import { useCallback, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { startSession, getDocuments, uploadDocument } from "@/lib/api";
import type { QuizConfig, ExamType, DifficultyMode, DocumentInfo } from "@/types/quiz";
import {
  FileTextIcon,
  PresentationIcon,
  FolderIcon,
  UploadCloudIcon,
  ClockIcon,
} from "@/components/ui/Icons";

const ALLOWED_TYPES = [".pdf", ".docx", ".pptx", ".txt"];

function FileIcon({ ext }: { ext: string }) {
  if (ext === "pptx") return <PresentationIcon className="w-5 h-5 text-orange-400" />;
  if (ext === "pdf" || ext === "docx" || ext === "txt") return <FileTextIcon className="w-5 h-5 text-violet-400" />;
  return <FolderIcon className="w-5 h-5 text-white/40" />;
}

export default function UploadPage() {
  const router = useRouter();
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [selectedDocIds, setSelectedDocIds] = useState<Set<string>>(new Set());
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [loadingDocs, setLoadingDocs] = useState(true);

  const [config, setConfig] = useState<QuizConfig>({
    examType: "mcq",
    numQuestions: 10,
    difficultyMode: "adaptive",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const fetchDocs = async () => {
    try {
      setLoadingDocs(true);
      const docs = await getDocuments();
      setDocuments(docs);
    } catch (e) {
      console.error("Failed to fetch documents", e);
    } finally {
      setLoadingDocs(false);
    }
  };

  useEffect(() => {
    fetchDocs();
  }, []);

  const handleUpload = async (file: File) => {
    setUploading(true);
    setError("");
    try {
      await uploadDocument(file);
      await fetchDocs();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  };

  const addFiles = useCallback(
    (incoming: FileList | File[]) => {
      const arr = Array.from(incoming).filter((f) => {
        const ext = "." + f.name.split(".").pop()?.toLowerCase();
        return ALLOWED_TYPES.includes(ext);
      });
      if (arr.length > 0) {
        // Upload one by one
        arr.forEach(f => handleUpload(f));
      }
    },
    []
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      addFiles(e.dataTransfer.files);
    },
    [addFiles]
  );

  const toggleDocSelection = (id: string) => {
    setSelectedDocIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleSubmit = async () => {
    if (selectedDocIds.size === 0) {
      setError("Please select at least one document.");
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      const { session_id } = await startSession(Array.from(selectedDocIds), config);
      router.push(`/quiz/${session_id}`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Initialization failed. Please try again.";
      setError(msg);
      setSubmitting(false);
    }
  };

  const difficultyOptions: { val: DifficultyMode; label: string; desc: string; color: string }[] = [
    { val: "adaptive", label: "Adaptive", desc: "Adjusts in real-time (recommended)", color: "#8b5cf6" },
    { val: "easy",     label: "Easy",     desc: "Remember & understand level",         color: "#34d399" },
    { val: "medium",   label: "Medium",   desc: "Apply level",                          color: "#fbbf24" },
    { val: "hard",     label: "Hard",     desc: "Analyze & evaluate level",             color: "#f87171" },
  ];

  return (
    <main className="min-h-screen py-12 px-4">
      {/* Nav */}
      <nav className="flex items-center justify-between max-w-4xl mx-auto mb-12">
        <Link href="/" className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: "linear-gradient(135deg, #7c3aed 0%, #4f46e5 100%)" }}>
            <span className="text-white font-bold text-sm">AQ</span>
          </div>
          <span className="font-bold text-lg tracking-tight text-white">
            Adaptive<span className="bg-clip-text text-transparent" style={{ backgroundImage: "linear-gradient(135deg, #c4b5fd, #22d3ee)" }}>IQ</span>
          </span>
        </Link>
        <Link href="/" className="text-sm text-white/50 hover:text-white transition-colors">
          ← Back
        </Link>
      </nav>

      <div className="max-w-4xl mx-auto">
        <div className="mb-10 animate-[fadeIn_0.5s_ease-out]">
          <p className="text-xs font-semibold uppercase tracking-widest text-white/40 mb-2">Step 1 of 2</p>
          <h1 className="text-4xl font-extrabold tracking-tight text-white mb-3">
            Select or upload study material
          </h1>
          <p className="text-white/50 text-lg">
            Choose from your library or add new documents to generate a quiz.
          </p>
        </div>

        <div className="grid lg:grid-cols-2 gap-6">
          {/* Library & Upload Zone */}
          <div className="space-y-6">
            <div
              id="upload-drop-zone"
              onDragEnter={() => setDragging(true)}
              onDragLeave={() => setDragging(false)}
              onDragOver={(e) => e.preventDefault()}
              onDrop={onDrop}
              className={`relative rounded-2xl border-2 border-dashed transition-all duration-200 cursor-pointer overflow-hidden ${uploading ? 'opacity-50 pointer-events-none' : ''}`}
              style={{
                borderColor: dragging ? "rgba(139,92,246,0.8)" : "rgba(255,255,255,0.12)",
                background: dragging
                  ? "rgba(139,92,246,0.1)"
                  : "rgba(255,255,255,0.03)",
                boxShadow: dragging ? "0 0 40px rgba(139,92,246,0.2)" : "none",
              }}
              onClick={() => document.getElementById("file-input")?.click()}
            >
              <input
                id="file-input"
                type="file"
                multiple
                accept=".pdf,.docx,.pptx,.txt"
                className="hidden"
                onChange={(e) => e.target.files && addFiles(e.target.files)}
              />
              <div className="p-8 text-center">
                <div className="mb-4 flex justify-center text-white/50">
                  {uploading
                    ? <ClockIcon className="w-10 h-10 animate-pulse" />
                    : dragging
                    ? <UploadCloudIcon className="w-10 h-10 text-violet-400" />
                    : <FolderIcon className="w-10 h-10" />}
                </div>
                <p className="text-white font-semibold mb-1">
                  {uploading ? "Uploading and processing..." : dragging ? "Drop files here" : "Upload new document"}
                </p>
                <p className="text-white/40 text-xs">PDF, DOCX, PPTX, TXT</p>
              </div>
            </div>

            {/* Document Library List */}
            <div className="rounded-2xl border border-white/10 bg-white/5 p-5 backdrop-blur-sm">
              <h2 className="font-bold text-white mb-4">Your Library</h2>
              {loadingDocs ? (
                <div className="text-white/40 text-center py-4 text-sm animate-pulse">Loading documents...</div>
              ) : documents.length === 0 ? (
                <div className="text-white/30 text-center py-4 text-sm">No documents found. Upload one above.</div>
              ) : (
                <div className="space-y-2 max-h-[300px] overflow-y-auto pr-2 custom-scrollbar">
                  {documents.map((doc) => {
                    const ext = doc.filename.split(".").pop()?.toLowerCase() ?? "";
                    const isSelected = selectedDocIds.has(doc.document_id);
                    return (
                      <div
                        key={doc.document_id}
                        onClick={() => toggleDocSelection(doc.document_id)}
                        className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-all ${
                          isSelected ? "border-purple-500/50 bg-purple-500/10" : "border-white/10 bg-white/5 hover:border-white/20"
                        }`}
                      >
                        <div className="mt-0.5"><FileIcon ext={ext} /></div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-white truncate pr-2">{doc.filename}</p>
                          <div className="flex gap-1 flex-wrap mt-1.5">
                            {doc.topics.slice(0, 2).map((t, i) => (
                              <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-white/10 text-white/70 truncate max-w-[100px]">{t}</span>
                            ))}
                            {doc.topics.length > 2 && <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-white/50">+{doc.topics.length - 2}</span>}
                          </div>
                        </div>
                        <div className="flex items-center justify-center w-5 h-5 mt-1 rounded border border-white/30 transition-colors"
                             style={{ background: isSelected ? "#8b5cf6" : "transparent", borderColor: isSelected ? "#8b5cf6" : "rgba(255,255,255,0.3)" }}>
                          {isSelected && <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Configuration Panel */}
          <div className="space-y-5">
            <div className="rounded-2xl p-6 border border-white/10 bg-white/5 backdrop-blur-sm">
              <h2 className="font-bold text-white mb-5 text-lg">Quiz Configuration</h2>

              {/* Exam Type */}
              <div className="mb-5">
                <label className="text-xs font-semibold uppercase tracking-widest text-white/40 block mb-3">
                  Question Type
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {(["mcq", "structured", "essay"] as ExamType[]).map((t) => (
                    <button
                      key={t}
                      id={`exam-type-${t}`}
                      onClick={() => setConfig((c) => ({ ...c, examType: t }))}
                      className="py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 border"
                      style={{
                        background: config.examType === t ? "rgba(139,92,246,0.25)" : "rgba(255,255,255,0.04)",
                        borderColor: config.examType === t ? "rgba(139,92,246,0.6)" : "rgba(255,255,255,0.1)",
                        color: config.examType === t ? "#c4b5fd" : "rgba(255,255,255,0.5)",
                      }}
                    >
                      {t === "mcq" ? "MCQ" : t === "structured" ? "Structured" : "Essay"}
                    </button>
                  ))}
                </div>
              </div>

              {/* Number of Questions */}
              <div className="mb-5">
                <label className="text-xs font-semibold uppercase tracking-widest text-white/40 block mb-3">
                  Number of Questions
                </label>
                <div className="grid grid-cols-4 gap-2">
                  {([5, 10, 20, 50] as const).map((n) => (
                    <button
                      key={n}
                      id={`num-questions-${n}`}
                      onClick={() => setConfig((c) => ({ ...c, numQuestions: n }))}
                      className="py-2.5 rounded-xl text-sm font-bold transition-all duration-200 border"
                      style={{
                        background: config.numQuestions === n ? "rgba(139,92,246,0.25)" : "rgba(255,255,255,0.04)",
                        borderColor: config.numQuestions === n ? "rgba(139,92,246,0.6)" : "rgba(255,255,255,0.1)",
                        color: config.numQuestions === n ? "#c4b5fd" : "rgba(255,255,255,0.5)",
                      }}
                    >
                      {n}
                    </button>
                  ))}
                </div>
              </div>

              {/* Difficulty */}
              <div className="mb-5">
                <label className="text-xs font-semibold uppercase tracking-widest text-white/40 block mb-3">
                  Difficulty Mode
                </label>
                <div className="space-y-2">
                  {difficultyOptions.map((d) => (
                    <button
                      key={d.val}
                      id={`diff-${d.val}`}
                      onClick={() => setConfig((c) => ({ ...c, difficultyMode: d.val }))}
                      className="w-full flex items-center justify-between p-3 rounded-xl border transition-all duration-200 text-left"
                      style={{
                        background: config.difficultyMode === d.val ? "rgba(139,92,246,0.2)" : "rgba(255,255,255,0.03)",
                        borderColor: config.difficultyMode === d.val ? "rgba(139,92,246,0.5)" : "rgba(255,255,255,0.05)",
                      }}
                    >
                      <div>
                        <div className={`text-sm font-bold flex items-center gap-1.5 ${config.difficultyMode === d.val ? "text-white" : "text-white/70"}`}>
                          <span className="w-2 h-2 rounded-full inline-block shrink-0" style={{ background: d.color }} />
                          {d.label}
                        </div>
                        <div className="text-xs text-white/40 mt-0.5 pl-3.5">{d.desc}</div>
                      </div>
                      {config.difficultyMode === d.val && (
                        <div className="w-2 h-2 rounded-full bg-purple-400 shadow-[0_0_10px_rgba(192,132,252,0.8)]" />
                      )}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Error Message */}
            {error && (
              <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm animate-[shake_0.5s_ease-in-out]">
                {error}
              </div>
            )}

            {/* Submit */}
            <button
              id="generate-quiz-btn"
              onClick={handleSubmit}
              disabled={submitting || selectedDocIds.size === 0}
              className={`w-full relative overflow-hidden rounded-2xl p-[2px] transition-transform active:scale-[0.98] ${
                submitting || selectedDocIds.size === 0 ? "opacity-50 cursor-not-allowed" : "hover:shadow-[0_0_30px_rgba(139,92,246,0.4)]"
              }`}
            >
              <div className="absolute inset-0 bg-gradient-to-r from-violet-600 via-fuchsia-600 to-cyan-500 animate-[spin_4s_linear_infinite]" style={{ opacity: submitting || selectedDocIds.size === 0 ? 0 : 1 }} />
              <div className="relative bg-[#0f172a] rounded-[14px] py-4 px-6 flex items-center justify-center gap-3">
                <span className="font-bold text-white text-lg">
                  {submitting ? "Initializing Session..." : "Generate Quiz"}
                </span>
                {!submitting && <span className="text-xl">→</span>}
              </div>
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
