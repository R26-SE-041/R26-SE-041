/**
 * API client — works identically on Expo native (React Native fetch)
 * and Expo web (browser fetch).
 *
 * Set EXPO_PUBLIC_API_URL in a .env file to override the backend address.
 * Default: http://localhost:8000  (for web dev / Android emulator)
 * For a physical device use your PC's LAN IP, e.g. http://192.168.1.x:8000
 */

import { API_BASE_URL } from "./config";
import { getAccessToken, getAccountUserId, invalidateAccessToken } from "./auth";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface OcrLine {
  /** Base64-encoded JPEG of the cropped line image */
  crop_b64: string;
  /** Raw text from TrOCR */
  raw_text: string;
  /** Visual OCR agent text (may mirror raw_text if agent skipped) */
  visual_text?: string;
  /** Final corrected text (may mirror raw_text if validation skipped) */
  final_text?: string;
  /** Confidence score from TrOCR beam search [0, 1] */
  confidence: number;
}

export interface ProcessResult {
  id?: string | null;
  /** Base64-encoded PNG of the original uploaded image */
  original_b64: string;
  /** Base64-encoded PNG of the SRCNN-enhanced image */
  enhanced_b64: string;
  /** Full extracted Sinhala text (newline-joined from all lines) */
  extracted_text: string;
  extracted_text_ta?: string;
  extracted_text_en?: string;
  /** Per-line OCR results with crop images */
  lines?: OcrLine[];
}

// ---------------------------------------------------------------------------
// Custom error class
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

/**
 * Upload an image to the backend for enhancement + OCR.
 *
 * @param uri     - Local file URI (from image picker or document picker)
 * @param name    - File name (used as FormData filename)
 * @param mimeType - MIME type of the image
 */
import { Platform } from "react-native";

export async function processImage(
  uri: string,
  name: string,
  mimeType: string
): Promise<ProcessResult> {
  const requestOwner = getAccountUserId();
  const formData = new FormData();
  
  if (Platform.OS === "web") {
    // On web, we must fetch the blob from the object URL
    const response = await fetch(uri);
    const blob = await response.blob();
    formData.append("file", blob, name);
  } else {
    // React Native's FormData accepts the blob-like object format
    formData.append("file", {
      uri,
      name,
      type: mimeType,
    } as unknown as Blob);
  }

  let response: Response;
  const token = await getAccessToken(requestOwner);
  try {
    response = await fetch(`${API_BASE_URL}/api/process`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    });
  } catch {
    throw new Error(
      "We could not connect to the reading service. Please check your connection and try again."
    );
  }

  if (!response.ok) {
    if (response.status === 401) invalidateAccessToken(token);
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // ignore JSON parse errors
    }
    throw new ApiError(response.status, detail);
  }

  return (await response.json()) as ProcessResult;
}

/**
 * Submit corrected OCR text back to the server for dataset collection.
 * 
 * @param crop_b64 - Base64 encoded cropped line image
 * @param corrected_text - The correct Sinhala text
 */
export async function submitOcrFeedback(
  crop_b64: string,
  corrected_text: string
): Promise<void> {
  let response: Response;
  const token = await getAccessToken();
  try {
    response = await fetch(`${API_BASE_URL}/api/feedback/ocr`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        crop_b64,
        corrected_text,
      }),
    });
  } catch {
    throw new Error("Could not reach the backend to submit feedback.");
  }

  if (!response.ok) {
    if (response.status === 401) invalidateAccessToken(token);
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }
}

