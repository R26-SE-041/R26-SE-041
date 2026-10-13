import { studioRequest } from "./studioClient";
import { STUDIO_API_ORIGIN } from "./config";

export interface PdfDocument {
  id: string;
  filename: string;
  size_bytes: number;
  status: "processing" | "ready" | "failed";
  error?: string | null;
  page_count?: number | null;
  skipped_pages: number;
  job_id: string;
}

export interface PdfSource {
  number: number;
  documentId: string;
  filename: string;
  page: number;
  excerpt: string;
}

export const MAX_PDF_BYTES = 15 * 1024 * 1024;
export const MAX_PDF_FILES = 10;
export const listPdfDocuments = (chatId: string) => studioRequest<PdfDocument[]>(
  `/studio/chats/${encodeURIComponent(chatId)}/documents`);
export const uploadPdfDocument = (chatId: string, filename: string, body: BodyInit) => studioRequest<PdfDocument>(
  `/studio/chats/${encodeURIComponent(chatId)}/documents?filename=${encodeURIComponent(filename)}`,
  { method: "POST", headers: { "Content-Type": "application/pdf" }, body }, STUDIO_API_ORIGIN);
export const removePdfDocument = (id: string) => studioRequest(`/studio/documents/${encodeURIComponent(id)}`, { method: "DELETE" });
export const retryPdfDocument = (id: string) => studioRequest<PdfDocument>(`/studio/documents/${encodeURIComponent(id)}/retry`, { method: "POST" });
export async function pdfPageUrl(documentId: string, page: number) {
  const result = await studioRequest<{ url: string }>(`/studio/documents/${encodeURIComponent(documentId)}/url`);
  return result.url.split("#")[0] + `#page=${Math.max(1, Math.floor(page))}`;
}

/** Retain intentional deselections; automatically select newly indexed uploads. */
export function reconcilePdfSelection(documents: PdfDocument[], selected: string[], known: Set<string>) {
  const ready = documents.filter(document => document.status === "ready").map(document => document.id);
  return ready.filter(id => selected.includes(id) || !known.has(id));
}
