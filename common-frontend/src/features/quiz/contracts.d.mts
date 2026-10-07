import type { Question, AnswerResult } from './types';
export function isOpenEnded(type: string): boolean;
export function isTerminal(question: Question, feedback: AnswerResult | null): boolean;
export function answerRequest(question: Question, answer: string, startedAt: number, now?: number): { q_id: string; answer: string; time_taken_sec: number };
export function advanceRequest(question: Question): { q_id: string };
