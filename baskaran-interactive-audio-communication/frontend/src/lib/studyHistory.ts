import { AUTH_REQUIRED } from './config'
import * as local from './historyDb'
import { saveHistory, listHistory, saveHistoryAudio, editHistoryAnswer, deleteCloudHistory } from './api'
import type { HistoryItem } from '@/types'

export const CLOUD_HISTORY = AUTH_REQUIRED
export interface HistoryEntry extends local.LocalHistoryEntry {
  cloud?: boolean
  hasAnswerAudio?: boolean
  hasQuestionAudio?: boolean
}
function entry(row: HistoryItem): HistoryEntry {
  return { id: row.id, createdAt: row.created_at, language: row.language,
    transcript: row.question, answer: row.answer, references: row.references,
    documentGrounded: row.document_grounded ?? true, cloud: true,
    hasAnswerAudio: row.has_audio, hasQuestionAudio: row.has_question_audio }
}
export async function listStudyHistory(): Promise<HistoryEntry[]> {
  return CLOUD_HISTORY ? (await listHistory()).map(entry) : local.listLocalHistory()
}
export async function addHistoryEntry(item: Omit<local.LocalHistoryEntry, 'id' | 'createdAt'>): Promise<HistoryEntry> {
  if (!CLOUD_HISTORY) return local.addLocalHistoryEntry(item)
  const row = await saveHistory(item.transcript, item.answer, item.language, item.references, item.answerAudio,
    { questionAudio: item.questionAudio, documentGrounded: item.documentGrounded })
  return { ...entry(row), questionAudio: item.questionAudio, answerAudio: item.answerAudio }
}
export async function updateHistoryAudio(id: string, audio: Blob) {
  if (CLOUD_HISTORY) await saveHistoryAudio(id, audio)
  else await local.updateLocalHistoryAudio(id, audio)
}
export async function updateHistoryAnswer(id: string, answer: string) {
  if (CLOUD_HISTORY) await editHistoryAnswer(id, answer)
  else await local.updateLocalHistoryAnswer(id, answer)
}
export async function deleteHistoryEntry(id: string) {
  if (CLOUD_HISTORY) await deleteCloudHistory(id)
  else await local.deleteLocalHistoryEntry(id)
}
export async function clearStudyHistory() {
  if (CLOUD_HISTORY) await deleteCloudHistory()
  else await local.clearLocalHistory()
}
export async function deviceHistoryCount() { return (await local.listLocalHistory()).length }
export async function importDeviceHistory() {
  if (!CLOUD_HISTORY) return
  // Anonymous browser history has no provable owner. Import only after explicit
  // confirmation; retain local originals until each entry succeeds in the cloud.
  for (const item of await local.listLocalHistory()) {
    await saveHistory(item.transcript, item.answer, item.language, item.references, item.answerAudio,
      { questionAudio: item.questionAudio, documentGrounded: item.documentGrounded,
        sourceId: item.id, createdAt: item.createdAt })
    await local.deleteLocalHistoryEntry(item.id)
  }
}
