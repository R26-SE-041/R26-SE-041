'use client'

import { useState } from 'react'
import { deleteDocument } from '@/lib/api'
import type { DocumentItem, FileType } from '@/types'

// ── File type config ──────────────────────────────────────────────────────────
const FILE_CONFIG: Record<FileType, { icon: string; label: string; color: string }> = {
  pdf:  { icon: '📄', label: 'PDF',  color: 'text-red-400 bg-red-500/10 border-red-500/25' },
  pptx: { icon: '📊', label: 'PPTX', color: 'text-orange-400 bg-orange-500/10 border-orange-500/25' },
  docx: { icon: '📝', label: 'DOCX', color: 'text-blue-400 bg-blue-500/10 border-blue-500/25' },
  xlsx: { icon: '📈', label: 'XLSX', color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/25' },
  txt:  { icon: '📃', label: 'TXT',  color: 'text-white/50 bg-white/5 border-white/15' },
  md:   { icon: '✍️', label: 'MD',   color: 'text-purple-400 bg-purple-500/10 border-purple-500/25' },
}

function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat('en-US', {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    }).format(new Date(iso))
  } catch {
    return iso
  }
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
      <div style={{
        textAlign: 'center', padding: '2rem 1rem',
        color: 'rgba(255,255,255,0.25)', fontSize: 13,
      }}>
        No documents uploaded yet
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {documents.map((doc, i) => {
        const ft = doc.file_type as FileType
        const cfg = FILE_CONFIG[ft] ?? FILE_CONFIG.txt
        const isDeleting = deletingId === doc.document_id

        return (
          <div
            key={doc.document_id}
            className="glass-card"
            style={{
              borderRadius: 14,
              padding: '12px 16px',
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              opacity: isDeleting ? 0.5 : 1,
              transition: 'opacity 0.2s ease',
              animationDelay: `${i * 40}ms`,
            }}
          >
            {/* File icon */}
            <div style={{
              width: 40, height: 40, borderRadius: 10, flexShrink: 0,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 18,
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.08)',
            }}>
              {cfg.icon}
            </div>

            {/* Info */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <p style={{
                fontSize: 13, fontWeight: 600, color: 'rgba(255,255,255,0.85)',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {doc.filename}
              </p>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 3 }}>
                {/* Type badge */}
                <span className={`text-[10px] font-bold border rounded-md px-1.5 py-0.5 ${cfg.color}`}>
                  {cfg.label}
                </span>
                {/* Chunk count */}
                <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)' }}>
                  {doc.chunk_count} chunks
                </span>
                {/* Date */}
                <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.25)' }}>
                  · {formatDate(doc.uploaded_at)}
                </span>
              </div>
            </div>

            {/* Delete button */}
            <button
              onClick={() => handleDelete(doc)}
              disabled={isDeleting}
              title="Delete document"
              style={{
                flexShrink: 0,
                width: 30, height: 30,
                borderRadius: 8,
                border: '1px solid rgba(239,68,68,0.2)',
                background: 'rgba(239,68,68,0.06)',
                color: 'rgba(248,113,113,0.7)',
                fontSize: 13,
                cursor: isDeleting ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                if (!isDeleting) {
                  e.currentTarget.style.background = 'rgba(239,68,68,0.15)'
                  e.currentTarget.style.color = 'rgba(248,113,113,1)'
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(239,68,68,0.06)'
                e.currentTarget.style.color = 'rgba(248,113,113,0.7)'
              }}
            >
              {isDeleting ? '…' : '🗑'}
            </button>
          </div>
        )
      })}
    </div>
  )
}
