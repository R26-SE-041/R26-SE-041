/**
 * Client-side history store for the unauthenticated /test study assistant.
 *
 * That page has no login and no backend history endpoint, so every voice
 * chat (question + transcript + answer + audio) is persisted locally in the
 * browser via IndexedDB instead.
 */

import type { ChunkReference, Language } from '@/types'
import type { StudyMode } from '@/components/ui/StudyModeSelector'

const DB_NAME = 'voicelearn-test-history'
const DB_VERSION = 1
const STORE_NAME = 'entries'

export interface LocalHistoryEntry {
  id: string
  createdAt: string
  studyMode: StudyMode
  language: Language
  transcript: string
  answer: string
  references: ChunkReference[]
  documentGrounded: boolean
  /** Raw microphone recording for the question, if it was asked by voice. */
  questionAudio?: Blob
  /** Synthesized speech for the answer, attached once TTS completes. */
  answerAudio?: Blob
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') {
      reject(new Error('IndexedDB is not available in this browser.'))
      return
    }
    const request = indexedDB.open(DB_NAME, DB_VERSION)
    request.onupgradeneeded = () => {
      const db = request.result
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const store = db.createObjectStore(STORE_NAME, { keyPath: 'id' })
        store.createIndex('createdAt', 'createdAt')
      }
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error ?? new Error('Could not open the local history database.'))
  })
}

export async function addLocalHistoryEntry(
  entry: Omit<LocalHistoryEntry, 'id' | 'createdAt'>,
): Promise<LocalHistoryEntry> {
  const record: LocalHistoryEntry = {
    ...entry,
    id: crypto.randomUUID(),
    createdAt: new Date().toISOString(),
  }
  const db = await openDb()
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    tx.objectStore(STORE_NAME).add(record)
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error ?? new Error('Could not save the history entry.'))
  })
  db.close()
  return record
}

export async function updateLocalHistoryAudio(id: string, answerAudio: Blob): Promise<void> {
  const db = await openDb()
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    const store = tx.objectStore(STORE_NAME)
    const getRequest = store.get(id)
    getRequest.onsuccess = () => {
      const existing = getRequest.result as LocalHistoryEntry | undefined
      if (existing) store.put({ ...existing, answerAudio })
    }
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error ?? new Error('Could not attach audio to the history entry.'))
  })
  db.close()
}

export async function updateLocalHistoryAnswer(id: string, answer: string): Promise<void> {
  const db = await openDb()
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    const store = tx.objectStore(STORE_NAME)
    const getRequest = store.get(id)
    getRequest.onsuccess = () => {
      const existing = getRequest.result as LocalHistoryEntry | undefined
      if (existing) store.put({ ...existing, answer })
    }
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error ?? new Error('Could not update the history answer.'))
  })
  db.close()
}

export async function listLocalHistory(): Promise<LocalHistoryEntry[]> {
  const db = await openDb()
  const items = await new Promise<LocalHistoryEntry[]>((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly')
    const request = tx.objectStore(STORE_NAME).getAll()
    request.onsuccess = () => resolve(request.result as LocalHistoryEntry[])
    request.onerror = () => reject(request.error ?? new Error('Could not load history.'))
  })
  db.close()
  return items.sort((a, b) => b.createdAt.localeCompare(a.createdAt))
}

export async function deleteLocalHistoryEntry(id: string): Promise<void> {
  const db = await openDb()
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    tx.objectStore(STORE_NAME).delete(id)
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error ?? new Error('Could not delete the history entry.'))
  })
  db.close()
}

export async function clearLocalHistory(): Promise<void> {
  const db = await openDb()
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    tx.objectStore(STORE_NAME).clear()
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error ?? new Error('Could not clear history.'))
  })
  db.close()
}
