export type Language = 'english' | 'tamil' | 'sinhala';
export interface Reference { document_id: string; filename: string; chunk_index: number; page: number | null; excerpt: string; score: number }
export interface TutorResponse { answer: string; enhanced_query?: string; references: Reference[] }
export interface AudioDocument { document_id: string; filename: string; file_type: string; chunk_count: number; uploaded_at: string }
export interface HistoryItem { id: string; question: string; answer: string; language: Language; references: Reference[]; has_audio: boolean; created_at: string }
export interface Turn { id: string; question: string; answer: string; language: Language; references: Reference[]; createdAt: string; historyId?: string; historyError?: string }
