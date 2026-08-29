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
  ArrowLeftIcon,
  ArrowRightIcon,
} from "@/components/ui/Icons";

const ALLOWED_TYPES = [".pdf", ".docx", ".pptx", ".txt", ".jpg", ".jpeg", ".png"];

function FileIcon({ ext }: { ext: string }) {
  if (ext === "pptx") return <PresentationIcon className="w-5 h-5 text-orange-400" />;
  if (ext === "pdf" || ext === "docx" || ext === "txt") return <FileTextIcon className="w-5 h-5 text-orange-600" />;
  return <FolderIcon className="w-5 h-5 text-stone-500" />;
}

export default function UploadPage() {
  const router = useRouter();
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [selectedDocIds, setSelectedDocIds] = useState<Set<string>>(new Set());
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [subjectMode, setSubjectMode] = useState<"al_bio" | "general">("al_bio");
  const [quizTopic, setQuizTopic] = useState("");

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
    const topic = quizTopic.trim();
    if (selectedDocIds.size === 0 && topic.length < 2) {
      setError("Please select at least one document or enter a topic.");
      return;
    }
    setError("");
    setSubmitting(true);
    const subject = subjectMode === "al_bio" ? "Sri Lankan G.C.E. A/L Biology" : "General";
    try {
      const { session_id } = await startSession(
        Array.from(selectedDocIds),
        config,
        topic.length >= 2 ? topic : undefined,
        subject
      );
      router.push(`/quiz/${session_id}`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Initialization failed. Please try again.";
      setError(msg);
      setSubmitting(false);
    }
  };

  const difficultyOptions: { val: DifficultyMode; label: string; desc: string; color: string }[] = [
    { val: "adaptive", label: "Adaptive", desc: "Adjusts in real-time (recommended)", color: "var(--primary)" },
    { val: "easy", label: "Easy", desc: "Remember & understand level", color: "var(--success)" },
    { val: "medium", label: "Medium", desc: "Apply level", color: "var(--warning)" },
    { val: "hard", label: "Hard", desc: "Analyze & evaluate level", color: "var(--danger)" },
  ];

  return (
    <main className="min-h-screen py-12 px-4">
      {/* Nav */}
      <nav className="flex items-center justify-between max-w-4xl mx-auto mb-12">
        <Link href="/" className="flex items-center gap-2.5">
          <div className="brand-mark w-8 h-8 rounded-lg">
            <span className="font-bold text-sm">AQ</span>
          </div>
          <span className="font-bold text-lg tracking-tight text-stone-900">
            Adaptive<span className="text-orange-700">IQ</span>
          </span>
        </Link>
        <Link href="/" className="flex items-center gap-1.5 text-sm text-stone-500 hover:text-stone-900 transition-colors">
          <ArrowLeftIcon /> Back
        </Link>
      </nav>

      <div className="max-w-4xl mx-auto">
        <div className="mb-10 animate-[fadeIn_0.5s_ease-out]">
          <p className="text-xs font-semibold uppercase tracking-widest text-stone-500 mb-2">Step 1 of 2</p>
          <h1 className="text-4xl font-semibold tracking-tight text-stone-900 mb-3">
            Select or upload study material
          </h1>
          <p className="text-stone-500 text-lg">
            Upload your study material or enter a specific topic to generate a quiz.
          </p>
        </div>

        <div className="mb-6 grid grid-cols-2 gap-2 rounded-xl border border-orange-900/15 bg-orange-900/5 p-1.5">
          <button
            type="button"
            onClick={() => setSubjectMode("al_bio")}
            className={`rounded-lg px-4 py-3 text-sm font-semibold transition-colors ${subjectMode === "al_bio" ? "bg-orange-600 text-white shadow-sm" : "text-stone-900/55 hover:text-stone-900"}`}
          >
            A/L Biology
          </button>
          <button
            type="button"
            onClick={() => setSubjectMode("general")}
            className={`rounded-lg px-4 py-3 text-sm font-semibold transition-colors ${subjectMode === "general" ? "bg-orange-600 text-white shadow-sm" : "text-stone-900/55 hover:text-stone-900"}`}
          >
            General
          </button>
        </div>

        <div className="grid lg:grid-cols-2 gap-6">
          {/* Library & Upload Zone */}
          <div className="space-y-6">
            <div className="rounded-2xl border border-orange-900/15 bg-orange-900/5 p-6">
              <label htmlFor="quiz-topic" className="mb-2 block text-sm font-semibold text-stone-900">
                Topic (Optional)
              </label>
              <p className="mb-4 text-sm leading-6 text-stone-900/45">
                {subjectMode === "al_bio" 
                  ? "Enter a clear topic such as cellular respiration, genetics, plant transport, or human reproduction."
                  : "Enter any general topic you would like to be tested on."}
              </p>
              <input
                id="quiz-topic"
                value={quizTopic}
                onChange={(event) => setQuizTopic(event.target.value)}
                maxLength={120}
                placeholder={subjectMode === "al_bio" ? "Example: Molecular basis of inheritance" : "Example: History of the Roman Empire"}
                className="input-glass"
              />
            </div>
            
            <div
              id="upload-drop-zone"
              onDragEnter={() => setDragging(true)}
              onDragLeave={() => setDragging(false)}
              onDragOver={(e) => e.preventDefault()}
              onDrop={onDrop}
              className={`relative rounded-2xl border-2 border-dashed transition-all duration-200 cursor-pointer overflow-hidden ${uploading ? 'opacity-50 pointer-events-none' : ''}`}
              style={{
                borderColor: dragging ? "rgba(216,101,59,0.72)" : "rgba(97,70,52,0.2)",
                background: dragging
                  ? "rgba(224,108,79,0.1)"
                  : "rgba(0,0,0,0.03)",
                boxShadow: dragging ? "0 0 40px rgba(224,108,79,0.2)" : "none",
              }}
              onClick={() => document.getElementById("file-input")?.click()}
            >
              <input
                id="file-input"
                type="file"
                multiple
                accept=".pdf,.docx,.pptx,.txt,.jpg,.jpeg,.png"
                className="hidden"
                onChange={(e) => e.target.files && addFiles(e.target.files)}
              />
              <div className="p-8 text-center">
                <div className="mb-4 flex justify-center text-stone-500">
                  {uploading
                    ? <ClockIcon className="w-10 h-10 animate-pulse" />
                    : dragging
                    ? <UploadCloudIcon className="w-10 h-10 text-orange-600" />
                    : <FolderIcon className="w-10 h-10" />}
                </div>
                <p className="text-stone-900 font-semibold mb-1">
                  {uploading ? "Uploading and processing..." : dragging ? "Drop files here" : "Upload new document"}
                </p>
                <p className="text-stone-500 text-xs">PDF, DOCX, PPTX, TXT, JPG, PNG</p>
              </div>
            </div>


            {/* Document Library List */}
            <div className="rounded-2xl border border-orange-900/15 bg-orange-900/5 p-5 backdrop-blur-sm">
              <h2 className="font-bold text-stone-900 mb-4">Your Library</h2>
              {loadingDocs ? (
                <div className="text-stone-500 text-center py-4 text-sm animate-pulse">Loading documents...</div>
              ) : documents.length === 0 ? (
                <div className="text-stone-400 text-center py-4 text-sm">No documents found. Upload one above.</div>
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
                          isSelected ? "border-orange-500/50 bg-orange-500/10" : "border-orange-900/15 bg-orange-900/5 hover:border-orange-900/20"
                        }`}
                      >
                        <div className="mt-0.5"><FileIcon ext={ext} /></div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-stone-900 truncate pr-2">{doc.filename}</p>
                          <div className="flex gap-1 flex-wrap mt-1.5">
                            {doc.topics.slice(0, 2).map((t, i) => (
                              <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-orange-900/10 text-stone-900/70 truncate max-w-[100px]">{t}</span>
                            ))}
                            {doc.topics.length > 2 && <span className="text-[10px] px-1.5 py-0.5 rounded bg-orange-900/5 text-stone-500">+{doc.topics.length - 2}</span>}
                          </div>
                        </div>
                        <div className="flex items-center justify-center w-5 h-5 mt-1 rounded border border-white/30 transition-colors"
                             style={{ background: isSelected ? "#e06c4f" : "transparent", borderColor: isSelected ? "#e06c4f" : "rgba(0,0,0,0.3)" }}>
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
            <div className="rounded-2xl p-6 border border-orange-900/15 bg-orange-900/5 backdrop-blur-sm">
              <h2 className="font-bold text-stone-900 mb-5 text-lg">Quiz Configuration</h2>

              {/* Exam Type */}
              <div className="mb-5">
                <label className="text-xs font-semibold uppercase tracking-widest text-stone-500 block mb-3">
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
                        background: config.examType === t ? "rgba(224,108,79,0.25)" : "rgba(0,0,0,0.04)",
                        borderColor: config.examType === t ? "rgba(224,108,79,0.6)" : "rgba(0,0,0,0.1)",
                        color: config.examType === t ? "#9a4327" : "rgba(0,0,0,0.5)",
                      }}
                    >
                      {t === "mcq" ? "MCQ" : t === "structured" ? "Structured" : "Essay"}
                    </button>
                  ))}
                </div>
              </div>

              {/* Number of Questions */}
              <div className="mb-5">
                <label className="text-xs font-semibold uppercase tracking-widest text-stone-500 block mb-3">
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
                        background: config.numQuestions === n ? "rgba(224,108,79,0.25)" : "rgba(0,0,0,0.04)",
                        borderColor: config.numQuestions === n ? "rgba(224,108,79,0.6)" : "rgba(0,0,0,0.1)",
                        color: config.numQuestions === n ? "#9a4327" : "rgba(0,0,0,0.5)",
                      }}
                    >
                      {n}
                    </button>
                  ))}
                </div>
              </div>

              {/* Difficulty */}
              <div className="mb-5">
                <label className="text-xs font-semibold uppercase tracking-widest text-stone-500 block mb-3">
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
                        background: config.difficultyMode === d.val ? "rgba(224,108,79,0.2)" : "rgba(0,0,0,0.03)",
                        borderColor: config.difficultyMode === d.val ? "rgba(224,108,79,0.5)" : "rgba(0,0,0,0.05)",
                      }}
                    >
                      <div>
                        <div className={`text-sm font-bold flex items-center gap-1.5 ${config.difficultyMode === d.val ? "text-stone-900" : "text-stone-900/70"}`}>
                          <span className="w-2 h-2 rounded-full inline-block shrink-0" style={{ background: d.color }} />
                          {d.label}
                        </div>
                        <div className="text-xs text-stone-500 mt-0.5 pl-3.5">{d.desc}</div>
                      </div>
                      {config.difficultyMode === d.val && (
                        <div className="w-2 h-2 rounded-full bg-orange-500" />
                      )}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Error Message */}
            {error && (
              <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-600 text-sm animate-[shake_0.5s_ease-in-out]">
                {error}
              </div>
            )}

            {/* Submit */}
            <button
              id="generate-quiz-btn"
              onClick={handleSubmit}
              disabled={submitting || (selectedDocIds.size === 0 && quizTopic.trim().length < 2)}
              className={`w-full btn-primary rounded-2xl py-4 ${submitting || (selectedDocIds.size === 0 && quizTopic.trim().length < 2) ? "opacity-50 cursor-not-allowed" : ""}`}
            >
              <div className="relative flex items-center justify-center gap-3">
                <span className="font-bold text-white text-lg">
                  {submitting ? "Initializing Session..." : "Generate Quiz"}
                </span>
                {!submitting && <ArrowRightIcon className="h-5 w-5" />}
              </div>
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
