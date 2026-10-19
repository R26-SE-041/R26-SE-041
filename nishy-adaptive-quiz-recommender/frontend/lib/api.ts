import { accessToken } from "./supabase";
/**
 * Typed API client for the Adaptive Quiz FastAPI backend.
 */
import type {
  StartSessionResponse,
  SessionStatusResponse,
  Question,
  SubmitAnswerRequest,
  SubmitAnswerResponse,
  AdvanceQuestionResponse,
  AnalyticsReport,
  QuizConfig,
  DocumentInfo,
  UploadDocumentResponse,
} from "@/types/quiz";

const BASE_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = await accessToken();
  const headers = new Headers(init?.headers);
  headers.set("Authorization", `Bearer ${token}`);
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, { ...init, headers, cache: "no-store" });
  } catch (networkErr) {
    throw new Error(
      "The quiz service is temporarily unavailable. Please try again."
    );
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    let msg = err.detail;
    if (typeof msg !== "string") {
      msg = JSON.stringify(msg);
    }
    throw new Error(msg ?? `API error ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function startSession(
  documentIds: string[],
  config: QuizConfig,
  topic?: string,
  subject: string = "Sri Lankan G.C.E. A/L Biology"
): Promise<StartSessionResponse> {
  const req = {
    document_ids: documentIds,
    topic: topic?.trim() || null,
    subject: subject,
    exam_type: config.examType,
    num_questions: config.numQuestions,
    difficulty_mode: config.difficultyMode,
    time_limit_min: config.timeLimitMin,
  };
  return apiFetch<StartSessionResponse>("/api/v1/session/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
}

export async function getDocuments(): Promise<DocumentInfo[]> {
  return apiFetch<DocumentInfo[]>("/api/v1/documents/");
}

export async function uploadDocument(file: File): Promise<UploadDocumentResponse> {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<UploadDocumentResponse>("/api/v1/documents/upload", {
    method: "POST",
    body: form,
  });
}

export async function getSessionStatus(sessionId: string): Promise<SessionStatusResponse> {
  return apiFetch<SessionStatusResponse>(`/api/v1/session/${sessionId}/status`);
}

export async function getCurrentQuestion(sessionId: string): Promise<Question> {
  return apiFetch<Question>(`/api/v1/quiz/${sessionId}/question`);
}

export async function retryQuestionGeneration(
  sessionId: string
): Promise<{ status: "ready" | "processing" }> {
  return apiFetch<{ status: "ready" | "processing" }>(
    `/api/v1/quiz/${sessionId}/retry-generation`,
    { method: "POST" }
  );
}

export async function submitAnswer(sessionId: string, req: SubmitAnswerRequest): Promise<SubmitAnswerResponse> {
  return apiFetch<SubmitAnswerResponse>(`/api/v1/quiz/${sessionId}/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
}

export async function advanceQuestion(sessionId: string, qId: string): Promise<AdvanceQuestionResponse> {
  return apiFetch<AdvanceQuestionResponse>(`/api/v1/quiz/${sessionId}/advance`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ q_id: qId }),
  });
}

export async function getAnalyticsReport(sessionId: string): Promise<AnalyticsReport> {
  return apiFetch<AnalyticsReport>(`/api/v1/analytics/${sessionId}/report`);
}

export async function submitFeedback(
  sessionId: string,
  rating: number,
  comment?: string
): Promise<{ status: string; message: string }> {
  return apiFetch(`/api/v1/analytics/${sessionId}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rating, comment: comment ?? null }),
  });
}

export interface HistoryItem {
  session_id: string; title: string | null; created_at: string; completed_at: string | null;
  exam_type: string; num_questions: number; difficulty_mode: string; status: string;
  topics_detected: string; deleted_at: string | null; final_score: number | null; answered: number;
}
export const getHistory = (deleted = false) => apiFetch<HistoryItem[]>(`/api/v1/history?deleted=${deleted}&limit=500`);
export const moveHistory = (id: string, restore = false) => apiFetch<{status: string}>(`/api/v1/history/${id}/${restore ? "restore" : "trash"}`, { method: "POST" });
