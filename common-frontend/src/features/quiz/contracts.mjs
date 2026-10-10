export function isOpenEnded(type) { return type === 'structured' || type === 'essay'; }
export function isTerminal(question, feedback) {
  if (!feedback) return false;
  return feedback.is_correct || feedback.attempts >= 4 || feedback.quiz_complete;
}
export function answerRequest(question, answer, startedAt, now = Date.now()) {
  return { q_id: question.q_id, answer: answer.trim(), time_taken_sec: Math.max(0, Math.round((now - startedAt) / 1000)) };
}
export function advanceRequest(question) {
  if (!isOpenEnded(question.q_type)) throw new Error('MCQ and fill-blank questions advance when their answer is finalized.');
  return { q_id: question.q_id };
}
