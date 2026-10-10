export function voiceForm(upload, language, sessionId) {
  const form = new FormData(); form.append('audio_file', upload.file, upload.name); form.append('language', language);
  if (sessionId) form.append('session_id', sessionId);
  return form;
}
export function historyForm(turn, audio) {
  const form = new FormData(); form.append('question',turn.question); form.append('answer',turn.answer); form.append('language',turn.language); form.append('references',JSON.stringify(turn.references||[]));
  if (audio) form.append('audio_file',audio,'answer.wav');
  return form;
}
