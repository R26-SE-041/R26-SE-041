// Type definitions for Adaptive Quiz Platform

export type ExamType = "mcq" | "structured" | "essay";
export type DifficultyMode = "easy" | "medium" | "hard" | "adaptive";
export type SessionStatus = "processing" | "ready" | "error";
export type BloomLevel =
  | "remember"
  | "understand"
  | "apply"
  | "analyze"
  | "evaluate"
  | "create";

// ── Document Library ──────────────────────────────────────────────

export interface DocumentInfo {
  document_id: string;
  filename: string;
  topics: string[];
  chunk_count: number;
  created_at: string;
}

export interface UploadDocumentResponse {
  document_id: string;
  message: string;
  topics: string[];
}

// ── Session ─────────────────────────────────────────────────────

export interface StartSessionResponse {
  session_id: string;
  status: SessionStatus;
  message: string;
}

export interface SessionStatusResponse {
  session_id: string;
  status: SessionStatus;
  topics_detected: string[];
  num_questions: number;
  message: string;
  chunk_count: number;
}

// ── Quiz ─────────────────────────────────────────────────────────

export interface MCQOptions {
  A: string;
  B: string;
  C: string;
  D: string;
}

export interface Question {
  q_id: string;
  q_index: number;
  total_questions: number;
  question: string;
  q_type: ExamType;
  options: MCQOptions | null;
  topic: string;
  bloom_level: BloomLevel;
  difficulty: number; // 0.0 - 1.0
  grounding_score: number;
  is_flagged: boolean;
}

export interface SubmitAnswerRequest {
  q_id?: string;         // optional — backend resolves from session state
  answer: string;
  time_taken_sec: number;
}

export interface SubmitAnswerResponse {
  is_correct: boolean;
  score: number;
  feedback: string;
  hint?: string | null;  // populated when incorrect (separate from feedback)
  hints_used: number;
  attempts: number;
  next_question_available: boolean;
  quiz_complete: boolean;
}

// ── Analytics ────────────────────────────────────────────────────

export interface ResourceLink {
  label: "English" | "Tamil" | "Sinhala" | string;
  title: string;
  url: string;
  source: string;
}

export interface WeakTopicRecommendation {
  topic: string;
  score_ratio: number;
  percentage: number;
  concept_notes: string[];
  resources: ResourceLink[];
}

export interface QuestionMarkDetail {
  q_num: number;
  topic: string;
  bloom: string;
  difficulty: number;
  is_correct: boolean;
  attempts: number;
  hints_used: number;
  marks: number;
  max_marks: number;
}

export interface AnalyticsReport {
  session_id: string;
  final_score: number;
  total_marks_earned?: number;
  total_marks_possible?: number;
  question_marks_detail?: QuestionMarkDetail[];
  total_questions: number;
  correct_count: number;
  topic_scores: Record<string, { correct: number; total: number }>;
  bloom_scores: Record<string, { correct: number; total: number }>;
  weak_topics: string[];
  strong_topics: string[];
  recommendations: WeakTopicRecommendation[];
  avg_time_per_question: number;
  difficulty_progression: number[];
  grounding_stats: {
    avg_grounding_score: number;
    flagged_count: number;
  };
  avg_attempts?: number;
  avg_hints_used?: number;
  total_time_min?: number;
}

// ── UI State ─────────────────────────────────────────────────────

export interface QuizConfig {
  examType: ExamType;
  numQuestions: 5 | 10 | 20 | 50;
  difficultyMode: DifficultyMode;
  timeLimitMin?: number;
}
