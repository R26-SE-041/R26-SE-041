'use client'

import { useState } from 'react'
import { deleteDocument } from '@/lib/api'
import type { DocumentItem, FileType } from '@/types'

const FILE_CONFIG: Record<FileType, { label: string; bg: string; color: string; border: string }> = {
  pdf:  { label: 'PDF',  bg: 'var(--c-red-soft)',   color: 'var(--c-red)',   border: 'var(--c-red-border)' },
  pptx: { label: 'PPTX', bg: '#FFF7ED',              color: '#C2410C',       border: 'rgba(234,88,12,0.2)' },
  docx: { label: 'DOCX', bg: 'var(--c-blue-soft)',  color: 'var(--c-blue)', border: 'var(--c-blue-border)' },
  xlsx: { label: 'XLSX', bg: 'var(--c-green-soft)', color: 'var(--c-green)',border: 'var(--c-green-border)' },
  txt:  { label: 'TXT',  bg: 'var(--c-inset)',      color: 'var(--c-ink-muted)', border: 'var(--c-border)' },
  md:   { label: 'MD',   bg: '#FAF5FF',             color: '#7C3AED',       border: 'rgba(124,58,237,0.2)' },
}

function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(iso))
  } catch { return iso }
}

interface DocumentListProps {
  documents: DocumentItem[]
  onDeleted: (id: string) => void
}

export function DocumentList({ documents, onDeleted }: DocumentListProps) {
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const handleDelete = async (doc: DocumentItem) => {
    if (!confirm(`Delete "${doc.filename}"? This cannot be undone.`)) return
    setDeletingId(doc.document_id)
    try {
      await deleteDocument(doc.document_id)
      onDeleted(doc.document_id)
    } catch (e) {
      console.error('Delete failed', e)
    } finally {
      setDeletingId(null)
    }
  }

  if (documents.length === 0) {
    return (
      <div className="text-center py-8 flex flex-col items-center gap-3">
        <div style={{ width: 40, height: 40, borderRadius: 10, background: 'var(--c-inset)', border: '1px solid var(--c-border)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
            stroke="var(--c-ink-faint)" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
        </div>
        <p className="text-sm" style={{ color: 'var(--c-ink-faint)' }}>No documents uploaded yet</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      {documents.map((doc) => {
        const ft = doc.file_type as FileType
        const cfg = FILE_CONFIG[ft] ?? FILE_CONFIG.txt
        const isDeleting = deletingId === doc.document_id

        return (
          <div key={doc.document_id}
            style={{
              borderRadius: 12, padding: '10px 14px',
              display: 'flex', alignItems: 'center', gap: 12,
              background: 'var(--c-card)',
              border: '1px solid var(--c-border)',
              boxShadow: 'var(--shadow-card)',
              opacity: isDeleting ? 0.5 : 1,
              transition: 'opacity 0.2s ease',
            }}>
            {/* File type badge */}
            <div style={{ width: 36, height: 36, borderRadius: 9, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: cfg.bg, border: `1px solid ${cfg.border}` }}>
              <span style={{ fontSize: 10, fontWeight: 800, letterSpacing: '0.05em', color: cfg.color }}>
                {cfg.label}
              </span>
            </div>

            {/* Info */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <p style={{ fontSize: 13, fontWeight: 500, color: 'var(--c-ink)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {doc.filename}
              </p>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 3 }}>
                <span style={{ fontSize: 11, color: 'var(--c-ink-faint)' }}>{doc.chunk_count} chunks</span>
                <span style={{ fontSize: 11, color: 'var(--c-ink-ghost)' }}>· {formatDate(doc.uploaded_at)}</span>
              </div>
            </div>

            {/* Delete */}
            <button onClick={() => handleDelete(doc)} disabled={isDeleting} title="Delete"
              style={{ flexShrink: 0, width: 28, height: 28, borderRadius: 7, border: '1px solid var(--c-red-border)', background: 'var(--c-red-soft)', color: 'var(--c-red)', cursor: isDeleting ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'all 0.15s ease' }}>
              {isDeleting ? (
                <div style={{ width: 12, height: 12, borderRadius: '50%', border: '1.5px solid var(--c-red-border)', borderTopColor: 'var(--c-red)', animation: 'spin 0.8s linear infinite' }} />
              ) : (
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="3 6 5 6 21 6" />
                  <path d="M19 6l-1 14H6L5 6" />
                  <path d="M10 11v6M14 11v6M9 6V4h6v2" />
                </svg>
              )}
            </button>
          </div>
        )
      })}
    </div>
  )
}
