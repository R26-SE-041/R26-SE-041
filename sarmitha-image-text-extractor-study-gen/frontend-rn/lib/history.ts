import { API_BASE_URL } from "./config";
import { getAccessToken, invalidateAccessToken } from "./auth";
import { ApiError, type OcrLine } from "./api";

export interface HistoryItem {
  id: string; created_at: string; filename: string; extracted_text: string;
  extracted_text_ta?: string; extracted_text_en?: string; lines?: OcrLine[];
  original_image_url?: string; enhanced_image_url?: string; image_error?: string;
}

async function historyRequest(path: string, method = "GET") {
  const token = await getAccessToken();
  if (!token) throw new Error("Please sign in to see your history.");
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/history${path}`, { method, headers: { Authorization: `Bearer ${token}` } });
  } catch { throw new Error("We could not reach your history. Please try again."); }
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 401) invalidateAccessToken(token);
    throw new ApiError(response.status, typeof data.detail === "string" ? data.detail : "Could not load history.");
  }
  return data;
}

export const loadHistory = (offset = 0): Promise<{ items: HistoryItem[]; has_more: boolean }> => historyRequest(`?offset=${offset}&limit=20`);
export const loadHistoryItem = (id: string): Promise<HistoryItem> => historyRequest(`/${encodeURIComponent(id)}`);
export const removeHistoryItem = (id: string) => historyRequest(`/${encodeURIComponent(id)}`, "DELETE");

export interface AccountEvent { id: string; event_type: "sign_up" | "sign_in" | "sign_out"; created_at: string; }
export async function loadAccountActivity(): Promise<AccountEvent[]> {
  const token = await getAccessToken();
  if (!token) return [];
  const response = await fetch(`${API_BASE_URL}/api/account/activity`, { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) {
    if (response.status === 401) invalidateAccessToken(token);
    throw new Error("Account activity is temporarily unavailable.");
  }
  return (await response.json()).items;
}
