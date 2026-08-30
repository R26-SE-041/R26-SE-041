'use client'

import { useCallback, useRef, useState } from 'react'
import { uploadDocument } from '@/lib/api'
import type { DocumentItem } from '@/types'

const ACCEPTED_EXTENSIONS = ['.pdf', '.pptx', '.docx', '.xlsx', '.txt', '.md']
const ACCEPTED_MIME = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'text/plain', 'text/markdown',
].join(',')

const FORMAT_BADGES = [
  { ext: 'PDF',  color: 'var(--c-red)',   bg: 'var(--c-red-soft)',   bdr: 'var(--c-red-border)' },
  { ext: 'PPTX', color: '#C2410C',        bg: '#FFF7ED',             bdr: 'rgba(234,88,12,0.2)' },
  { ext: 'DOCX', color: 'var(--c-blue)',  bg: 'var(--c-blue-soft)',  bdr: 'var(--c-blue-border)' },
  { ext: 'XLSX', color: 'var(--c-green)', bg: 'var(--c-green-soft)', bdr: 'var(--c-green-border)' },
  { ext: 'TXT',  color: 'var(--c-ink-muted)', bg: 'var(--c-inset)', bdr: 'var(--c-border)' },
  { ext: 'MD',   color: '#7C3AED',        bg: '#FAF5FF',             bdr: 'rgba(124,58,237,0.2)' },
]

interface UploadZoneProps {
  onUploaded: (doc: DocumentItem) => void
}

export function UploadZone({ onUploaded }: UploadZoneProps) {
  const [dragging, setDragging]   = useState(false)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress]   = useState(0)
  const [error, setError]         = useState<string | null>(null)
  const [fileName, setFileName]   = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = useCallback(async (file: File) => {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase()
    if (!ACCEPTED_EXTENSIONS.includes(ext)) {
      setError(`'${ext}' is not supported. Use: ${ACCEPTED_EXTENSIONS.join(', ')}`)
      return
    }
    if (file.size > 50 * 1024 * 1024) { setError('File exceeds the 50 MB limit'); return }

    setError(null); setFileName(file.name); setUploading(true); setProgress(10)
    const tick = (v: number) => setTimeout(() => setProgress(v), 600)
    tick(30); tick(55); tick(75)

    try {
      const doc = await uploadDocument(file)
      setProgress(100)
      setTimeout(() => { onUploaded(doc); setUploading(false); setProgress(0); setFileName(null) }, 500)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
      setUploading(false); setProgress(0)
    }
  }, [onUploaded])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }, [handleFile])

  return (
    <div className="flex flex-col gap-3">
      {/* Drop zone */}
      <div id="upload-zone" role="button" tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => !uploading && inputRef.current?.click()}
        style={{
          background: dragging ? 'var(--c-blue-soft)' : 'var(--c-inset)',
          borderColor: dragging ? 'var(--c-blue)' : uploading ? 'var(--c-blue-border)' : 'var(--c-border-md)',
          transform: dragging ? 'scale(1.012)' : 'scale(1)',
          transition: 'all 0.2s ease',
          border: '2px dashed',
          borderRadius: '16px',
          padding: '2rem 1.5rem',
          cursor: uploading ? 'default' : 'pointer',
          textAlign: 'center',
        }}>
        <input ref={inputRef} type="file" accept={ACCEPTED_MIME} className="hidden"
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])} />

        {/* Icon */}
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '1rem' }}>
          <div style={{ width: 48, height: 48, borderRadius: 12, background: dragging ? 'var(--c-blue-soft)' : 'var(--c-card)', border: `1px solid ${dragging ? 'var(--c-blue-border)' : 'var(--c-border)'}`, display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'all 0.2s' }}>
            {uploading ? (
              <div style={{ width: 20, height: 20, borderRadius: '50%', border: '2px solid var(--c-blue-border)', borderTopColor: 'var(--c-blue)', animation: 'spin 0.8s linear infinite' }} />
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
                stroke={dragging ? 'var(--c-blue)' : 'var(--c-ink-faint)'} strokeWidth={1.8}
                strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
            )}
          </div>
        </div>

        <p style={{ fontSize: 14, fontWeight: 500, color: 'var(--c-ink)', marginBottom: 4 }}>
          {uploading ? `Uploading ${fileName}…` : dragging ? 'Drop it here!' : 'Drop your lecture file here'}
        </p>
        <p style={{ fontSize: 12, color: 'var(--c-ink-faint)' }}>
          or click to browse · PDF, PPTX, DOCX, XLSX, TXT, MD · max 50 MB
        </p>

        {uploading && (
          <div style={{ marginTop: 14, height: 3, borderRadius: 9999, background: 'var(--c-border)', overflow: 'hidden' }}>
            <div style={{ height: '100%', borderRadius: 9999, background: 'var(--c-blue)', width: `${progress}%`, transition: 'width 0.5s ease' }} />
          </div>
        )}
      </div>

      {/* Format badges */}
      {!uploading && (
        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', justifyContent: 'center' }}>
          {FORMAT_BADGES.map(({ ext, bg, color, bdr }) => (
            <span key={ext} style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.06em', background: bg, color, border: `1px solid ${bdr}`, borderRadius: 6, padding: '3px 8px' }}>
              {ext}
            </span>
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, background: 'var(--c-red-soft)', border: '1px solid var(--c-red-border)', borderRadius: 10, padding: '10px 14px' }}>
          <span style={{ color: 'var(--c-red)', fontSize: 14, flexShrink: 0 }}>⚠</span>
          <p style={{ fontSize: 13, color: 'var(--c-red)', lineHeight: 1.5 }}>{error}</p>
        </div>
      )}
    </div>
  )
}
