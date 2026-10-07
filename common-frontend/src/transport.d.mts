export class ApiError extends Error { status: number; constructor(message: string, status: number); }
export function messageFrom(payload: unknown, fallback: string): string;
export function readResponse(response: Response, label: string, kind?: 'json' | 'blob'): Promise<unknown>;
