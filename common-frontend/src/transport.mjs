export class ApiError extends Error {
  constructor(message, status) { super(message); this.name = 'ApiError'; this.status = status; }
}
export function messageFrom(payload, fallback) {
  if (typeof payload?.detail === 'string') return payload.detail;
  if (typeof payload?.error === 'string') return payload.error;
  if (Array.isArray(payload?.detail)) return payload.detail.map(item => item.msg || 'Invalid input').join('; ');
  if (typeof payload?.detail?.error === 'string') return payload.detail.error;
  return fallback;
}
export async function readResponse(response, label, kind = 'json') {
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new ApiError(messageFrom(data, `${label}: request failed (${response.status}).`), response.status);
  }
  if (response.status === 204) return undefined;
  if (kind === 'blob') return response.blob();
  return response.json();
}
