export type Exam = 'mcq' | 'fill_blank' | 'structured' | 'essay';
export interface Document { document_id: string; filename: string; topics: string[]; chunk_count: number; created_at: string }
export interface Question { q_id: string; q_index: number; total_questions: number; question: string; q_type: Exam; options: Record<string,string> | null; topic: string; bloom_level: string; difficulty: number; grounding_score: number; grounding_status: string; source_file: string; page_number: number; is_flagged: boolean }
export interface AnswerResult { is_correct: boolean; score: number; feedback: string; hint: string | null; hints_used: number; attempts: number; next_question_available: boolean; quiz_complete: boolean; correct_answer: string | null; correct_answer_text: string | null; explanation: string | null }
export interface QuestionMark { q_num: number; topic: string; q_type?: string; bloom: string; difficulty: number; is_correct: boolean; attempts: number; hints_used: number; marks: number; max_marks: number; question?: string; options?: Record<string,string>; student_answer?: string; correct_answer?: string; model_answer?: string; attempt_history?: { attempt: number; answer: string; is_correct: boolean; hint?: string }[] }
export interface Report {
  session_id: string; final_score: number; total_marks_earned: number | null; total_marks_possible: number | null;
  question_marks_detail: QuestionMark[] | null; total_questions: number; total_answered: number; correct_count: number;
  topic_scores: Record<string,{ correct: number; total: number }>; bloom_scores: Record<string,{ correct: number; total: number }>;
  difficulty_progression: number[]; avg_attempts: number; avg_hints_used: number; total_time_min: number;
  weak_topics: string[]; strong_topics: string[]; recommendations: { topic: string; recommendation_type?: string; percentage?: number; concept_notes: string[]; resources: { title: string; url: string; label: string; source?: string }[] }[];
  avg_grounding_score: number; flagged_questions_count: number; flagged_questions_pct: number; recommendations_pending: boolean;
}
export interface SavedSession { id: string; createdAt: string; title: string; complete: boolean; question?: Question; feedback?: AnswerResult | null; report?: Report | null; timeLimit?: number; startedAt: number }
