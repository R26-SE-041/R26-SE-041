'use client'

import { useCallback, useRef, useState } from 'react'
import { uploadDocument } from '@/lib/api'
import type { DocumentItem } from '@/types'

// ── Supported formats ─────────────────────────────────────────────────────────
const ACCEPTED_EXTENSIONS = ['.pdf', '.pptx', '.docx', '.xlsx', '.txt', '.md']
const ACCEPTED_MIME = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'text/plain',
  'text/markdown',
].join(',')

const FORMAT_BADGES = [
  { ext: 'PDF',  color: 'from-red-500/20 to-red-600/10 border-red-500/30 text-red-400' },
  { ext: 'PPTX', color: 'from-orange-500/20 to-orange-600/10 border-orange-500/30 text-orange-400' },
  { ext: 'DOCX', color: 'from-blue-500/20 to-blue-600/10 border-blue-500/30 text-blue-400' },
  { ext: 'XLSX', color: 'from-emerald-500/20 to-emerald-600/10 border-emerald-500/30 text-emerald-400' },
  { ext: 'TXT',  color: 'from-white/10 to-white/5 border-white/15 text-white/50' },
  { ext: 'MD',   color: 'from-purple-500/20 to-purple-600/10 border-purple-500/30 text-purple-400' },
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
    const maxBytes = 50 * 1024 * 1024
    if (file.size > maxBytes) {
      setError('File exceeds the 50 MB limit')
      return
    }

    setError(null)
    setFileName(file.name)
    setUploading(true)
    setProgress(10)

    // Fake progress stages while waiting for server
    const tick = (v: number) => setTimeout(() => setProgress(v), 600)
    tick(30); tick(55); tick(75)

    try {
      const doc = await uploadDocument(file)
      setProgress(100)
      setTimeout(() => {
        onUploaded(doc)
        setUploading(false)
        setProgress(0)
        setFileName(null)
      }, 500)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
      setUploading(false)
      setProgress(0)
    }
  }, [onUploaded])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }, [handleFile])

  return (
    <div className="flex flex-col gap-3">
      {/* ── Drop zone ─────────────────────────────────────────────── */}
      <div
        id="upload-zone"
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => !uploading && inputRef.current?.click()}
        style={{
          background: dragging
            ? 'rgba(99,102,241,0.08)'
            : 'rgba(255,255,255,0.025)',
          borderColor: dragging
            ? 'rgba(99,102,241,0.6)'
            : uploading
            ? 'rgba(99,102,241,0.35)'
            : 'rgba(255,255,255,0.1)',
          transform: dragging ? 'scale(1.012)' : 'scale(1)',
          transition: 'all 0.2s ease',
          border: '2px dashed',
          borderRadius: '20px',
          padding: '2rem',
          cursor: uploading ? 'default' : 'pointer',
          textAlign: 'center',
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_MIME}
          className="hidden"
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
        />

        {/* Icon */}
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '1rem' }}>
          <div style={{
            width: 56, height: 56, borderRadius: 16,
            background: 'linear-gradient(135deg, rgba(99,102,241,0.2), rgba(168,85,247,0.15))',
            border: '1px solid rgba(99,102,241,0.3)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 24,
            boxShadow: uploading ? '0 0 30px rgba(99,102,241,0.25)' : 'none',
            transition: 'box-shadow 0.3s ease',
          }}>
            {uploading ? '⚙️' : dragging ? '📥' : '📂'}
          </div>
        </div>

        {/* Text */}
        <p style={{ fontSize: 15, fontWeight: 600, color: 'rgba(255,255,255,0.85)', marginBottom: 4 }}>
          {uploading
            ? `Uploading ${fileName}…`
            : dragging
            ? 'Drop it here!'
            : 'Drop your lecture file here'}
        </p>
        <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.35)' }}>
          or click to browse · PDF, PPTX, DOCX, XLSX, TXT, MD · max 50 MB
        </p>

        {/* Progress bar */}
        {uploading && (
          <div style={{ marginTop: 16, height: 4, borderRadius: 9999, background: 'rgba(255,255,255,0.07)', overflow: 'hidden' }}>
            <div style={{
              height: '100%',
              borderRadius: 9999,
              background: 'linear-gradient(90deg, #6366f1, #a855f7)',
              width: `${progress}%`,
              transition: 'width 0.5s ease',
            }} />
          </div>
        )}
      </div>

      {/* ── Format badges ──────────────────────────────────────────── */}
      {!uploading && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'center' }}>
          {FORMAT_BADGES.map(({ ext, color }) => (
            <span
              key={ext}
              className={`inline-flex items-center bg-gradient-to-br ${color} border rounded-lg px-2.5 py-1 text-[10px] font-bold tracking-wider`}
            >
              {ext}
            </span>
          ))}
        </div>
      )}

      {/* ── Error ─────────────────────────────────────────────────── */}
      {error && (
        <div style={{
          display: 'flex', alignItems: 'flex-start', gap: 8,
          background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)',
          borderRadius: 12, padding: '10px 14px',
        }}>
          <span style={{ color: '#f87171', fontSize: 14, flexShrink: 0 }}>⚠</span>
          <p style={{ fontSize: 13, color: '#f87171', lineHeight: 1.5 }}>{error}</p>
        </div>
      )}
    </div>
  )
}
