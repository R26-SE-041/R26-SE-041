// Type definitions for Adaptive Quiz Platform

export type ExamType = "mcq" | "fill_blank" | "structured" | "essay";
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
  is_topic_session?: boolean;
}

// ── Quiz ─────────────────────────────────────────────────────────

export interface MCQOptions {
  "1": string;
  "2": string;
  "3": string;
  "4": string;
  "5": string;
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
  grounding_status: "grounded" | "topic_model";
  source_file: string;
  page_number: number;
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
  correct_answer?: string | null;
  correct_answer_text?: string | null;
  explanation?: string | null;
}

export interface AdvanceQuestionResponse {
  quiz_complete: boolean;
  result: SubmitAnswerResponse;
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
  recommendation_type?: "review" | "enrichment";
  score_ratio: number;
  percentage: number;
  concept_notes: string[];
  resources: ResourceLink[];
}

export interface QuestionMarkDetail {
  q_num: number;
  topic: string;
  q_type?: ExamType;
  bloom: string;
  difficulty: number;
  is_correct: boolean;
  attempts: number;
  hints_used: number;
  marks: number;
  max_marks: number;
  question?: string;
  options?: Record<string, string>;
  student_answer?: string;
  correct_answer?: string;
  model_answer?: string;
  attempt_history?: Array<{
    attempt: number;
    answer: string;
    is_correct: boolean;
    hint?: string | null;
  }>;
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
  recommendations_pending?: boolean;
}

// ── UI State ─────────────────────────────────────────────────────

export interface QuizConfig {
  examType: ExamType;
  numQuestions: 5 | 10 | 20 | 50;
  difficultyMode: DifficultyMode;
  timeLimitMin?: number;
}
