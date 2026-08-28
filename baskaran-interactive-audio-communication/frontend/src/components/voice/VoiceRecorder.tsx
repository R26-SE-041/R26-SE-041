'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { clsx } from 'clsx'
import { useVoiceRecorder } from '@/hooks/useVoiceRecorder'
import type { Language, TranscribeResponse } from '@/types'
import { transcribeAudio } from '@/lib/api'

interface VoiceRecorderProps {
  language: Language
  onTranscript: (result: TranscribeResponse) => void
  onError: (msg: string) => void
  disabled?: boolean
}

/* ── Waveform bars ── */
function LiveWaveform({ bins, active }: { bins: number[]; active: boolean }) {
  return (
    <div className="flex items-end justify-center gap-[3px]" style={{ height: 36 }} aria-hidden>
      {bins.map((amplitude, i) => {
        const pct = active
          ? Math.max(5, amplitude * 100)
          : 10 + Math.sin(i * 0.6 + Date.now() * 0.001) * 4
        return (
          <div
            key={i}
            className="rounded-full transition-all"
            style={{
              width: 3,
              height: `${pct}%`,
              background: active ? '#EA4335' : '#D1D1D6',
              transitionDuration: active ? '60ms' : '800ms',
            }}
          />
        )
      })}
    </div>
  )
}

/* ── Icons ── */
function MicIcon({ size = 26 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="22" />
      <line x1="9"  y1="22" x2="15" y2="22" />
    </svg>
  )
}

function StopIcon() {
  return <div className="w-5 h-5 rounded bg-white" style={{ borderRadius: 4 }} />
}

function Spinner() {
  return (
    <div className="w-6 h-6 rounded-full border-2 border-sand-300 border-t-blue-500 animate-spin" />
  )
}

function PlayIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
      <polygon points="5 3 19 12 5 21 5 3" />
    </svg>
  )
}

function PauseIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
      <rect x="6" y="4" width="4" height="16" rx="1" />
      <rect x="14" y="4" width="4" height="16" rx="1" />
    </svg>
  )
}

function SendIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  )
}

function RetryIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <polyline points="1 4 1 10 7 10" />
      <path d="M3.51 15a9 9 0 1 0 .49-3.87" />
    </svg>
  )
}

function UploadIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="17 8 12 3 7 8" />
      <line x1="12" y1="3" x2="12" y2="15" />
    </svg>
  )
}

/* ── Audio Preview Player ── */
function AudioPreview({ blob, durationMs }: { blob: Blob; durationMs: number }) {
  const audioRef = useRef<HTMLAudioElement>(null)
  const [playing, setPlaying] = useState(false)
  const [progress, setProgress] = useState(0)
  const [currentTime, setCurrentTime] = useState(0)

  useEffect(() => {
    const url = URL.createObjectURL(blob)
    if (audioRef.current) {
      audioRef.current.src = url
      audioRef.current.load()
    }
    return () => URL.revokeObjectURL(url)
  }, [blob])

  const togglePlay = () => {
    const el = audioRef.current
    if (!el) return
    if (playing) el.pause()
    else el.play()
  }

  const handleTimeUpdate = () => {
    const el = audioRef.current
    if (!el) return
    const dur = isFinite(el.duration) ? el.duration : durationMs / 1000
    setCurrentTime(el.currentTime)
    setProgress(dur > 0 ? (el.currentTime / dur) * 100 : 0)
  }

  const handleSeek = (e: React.MouseEvent<HTMLDivElement>) => {
    const el = audioRef.current
    if (!el) return
    const dur = isFinite(el.duration) ? el.duration : durationMs / 1000
    if (!dur) return
    const rect = e.currentTarget.getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
    el.currentTime = ratio * dur
    setProgress(ratio * 100)
  }

  const fmt = (s: number) =>
    `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(Math.floor(s % 60)).padStart(2, '0')}`

  const totalSec = durationMs / 1000

  return (
    <div className="w-full nb-inset p-4 flex flex-col gap-3">
      <audio
        ref={audioRef}
        preload="metadata"
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => { setPlaying(false); setProgress(100) }}
        onTimeUpdate={handleTimeUpdate}
      />

      <div className="flex items-center gap-3">
        <button
          id="audio-preview-play-btn"
          type="button"
          onClick={togglePlay}
          className="w-9 h-9 rounded-full flex items-center justify-center transition-all hover:scale-105 active:scale-95 flex-shrink-0"
          style={{ background: '#1A73E8', color: '#fff' }}
          aria-label={playing ? 'Pause' : 'Play'}
        >
          {playing ? <PauseIcon /> : <PlayIcon />}
        </button>

        <div className="flex-1 flex flex-col gap-1.5">
          <div
            className="w-full h-1.5 rounded-full cursor-pointer overflow-hidden"
            style={{ background: '#DBD8CC' }}
            onClick={handleSeek}
            role="slider"
            aria-label="Audio progress"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(progress)}
          >
            <div
              className="h-full rounded-full transition-all duration-100"
              style={{ width: `${progress}%`, background: '#1A73E8' }}
            />
          </div>
          <div className="flex justify-between text-[10px] font-mono text-ink-faint">
            <span>{fmt(currentTime)}</span>
            <span>{fmt(totalSec)}</span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-1.5 text-xs font-medium" style={{ color: '#34A853' }}>
        <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: '#34A853' }} />
        Recording ready — review before submitting
      </div>
    </div>
  )
}

/* ── Main ── */
export function VoiceRecorder({ language, onTranscript, onError, disabled = false }: VoiceRecorderProps) {
  const { recordingState, audioBlob, frequencyBins, durationMs, startRecording, stopRecording, clearRecording } = useVoiceRecorder()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [elapsed, setElapsed] = useState(0)
  const [previewBlob, setPreviewBlob] = useState<Blob | null>(null)
  const [previewDuration, setPreviewDuration] = useState(0)
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null)
  const [isTranscribing, setIsTranscribing] = useState(false)

  /* Live timer */
  useEffect(() => {
    if (recordingState !== 'recording') { setElapsed(0); return }
    const t = setInterval(() => setElapsed((s) => s + 1), 1000)
    return () => clearInterval(t)
  }, [recordingState])

  /* When recording finishes → show preview */
  useEffect(() => {
    if (recordingState === 'done' && audioBlob) {
      setPreviewBlob(audioBlob)
      setPreviewDuration(durationMs)
      setUploadedFileName(null)
    }
  }, [recordingState, audioBlob, durationMs])

  const handleSubmit = useCallback(async () => {
    if (!previewBlob) return
    setIsTranscribing(true)
    try {
      const result = await transcribeAudio(previewBlob, language, uploadedFileName ?? 'recording.webm')
      onTranscript(result)
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Transcription failed')
    } finally {
      setIsTranscribing(false)
      setPreviewBlob(null)
      setPreviewDuration(0)
      setUploadedFileName(null)
      clearRecording()
    }
  }, [previewBlob, language, uploadedFileName, onTranscript, onError, clearRecording])

  const handleReRecord = useCallback(() => {
    setPreviewBlob(null)
    setPreviewDuration(0)
    setUploadedFileName(null)
    clearRecording()
  }, [clearRecording])

  const handleAudioUpload = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    clearRecording()
    setPreviewBlob(file)
    setPreviewDuration(0)
    setUploadedFileName(file.name)
  }, [clearRecording])

  const toggle = useCallback(() => {
    if (recordingState === 'recording') stopRecording()
    else if (recordingState === 'idle') startRecording()
  }, [recordingState, startRecording, stopRecording])

  const isRecording  = recordingState === 'recording'
  const isProcessing = recordingState === 'processing'
  const isPreview    = !!(previewBlob && !isTranscribing)
  const btnDisabled  = disabled || isProcessing || isTranscribing || isPreview

  const fmt = (s: number) =>
    `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`

  return (
    <div className="flex flex-col items-center gap-5 w-full">
      <input
        ref={fileInputRef}
        type="file"
        accept="audio/wav,audio/x-wav,audio/mpeg,audio/mp3,audio/mp4,audio/m4a,audio/x-m4a,audio/webm,audio/ogg,.wav,.mp3,.m4a,.webm,.ogg"
        onChange={handleAudioUpload}
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
      />

      {/* ── Mic area (hidden during preview) ── */}
      {!isPreview && (
        <div className="flex flex-col items-center gap-4 w-full">

          {/* Mic button */}
          <div className="relative flex items-center justify-center" style={{ width: 120, height: 120 }}>
            {/* Recording pulse ring */}
            {isRecording && (
              <>
                <span className="absolute inset-0 rounded-full border-2 border-red-400 animate-record-ring opacity-60" />
                <span className="absolute rounded-full border border-red-300 animate-record-ring opacity-30"
                  style={{ inset: '-12px', animationDelay: '0.5s' }} />
              </>
            )}

            <button
              id="voice-record-btn"
              type="button"
              aria-label={isRecording ? 'Stop recording' : 'Start recording'}
              onClick={toggle}
              disabled={btnDisabled}
              className={clsx(
                'relative z-10 w-20 h-20 rounded-full flex items-center justify-center transition-all duration-200',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:ring-offset-4',
                'focus-visible:ring-offset-sand-100 disabled:opacity-40 disabled:pointer-events-none',
                isRecording
                  ? 'scale-110'
                  : 'hover:scale-105 active:scale-95',
              )}
              style={{
                background: isRecording ? '#EA4335' : '#FFFFFF',
                color: isRecording ? '#FFFFFF' : '#1C1C1E',
                boxShadow: isRecording
                  ? '0 0 0 0 rgba(234,67,53,0.3), 0 6px 24px rgba(234,67,53,0.2), 0 2px 8px rgba(0,0,0,0.08)'
                  : '0 4px 16px rgba(0,0,0,0.10), 0 1px 4px rgba(0,0,0,0.06), inset 0 1px 0 rgba(255,255,255,0.9)',
              }}
            >
              {(isProcessing || isTranscribing)
                ? <Spinner />
                : isRecording
                  ? <StopIcon />
                  : <MicIcon />
              }
            </button>
          </div>

          {/* Status text */}
          <div className="flex flex-col items-center gap-1.5">
            {isRecording ? (
              <div className="flex items-center gap-2">
                <span className="nb-dot nb-dot-red" />
                <span className="text-xs font-semibold tracking-wide" style={{ color: '#EA4335' }}>
                  Recording — speak now
                </span>
              </div>
            ) : (isProcessing || isTranscribing) ? (
              <p className="text-xs font-medium text-ink-muted animate-pulse">
                {isTranscribing ? 'Transcribing…' : 'Processing…'}
              </p>
            ) : (
              <p className="text-xs text-ink-faint">Tap to speak</p>
            )}

            {isRecording && (
              <span className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-mono font-semibold"
                style={{ background: 'rgba(234,67,53,0.08)', color: '#EA4335', border: '1px solid rgba(234,67,53,0.2)' }}>
                {fmt(elapsed)}
              </span>
            )}
          </div>

          {/* Waveform */}
          <div className={clsx(
            'w-full rounded-xl px-4 py-3 transition-all duration-300',
            isRecording ? 'bg-red-50 border border-red-100' : 'nb-inset'
          )}>
            <LiveWaveform bins={frequencyBins} active={isRecording} />
          </div>

          {/* Upload audio file */}
          {!isRecording && !isProcessing && !isTranscribing && (
            <button
              id="voice-upload-audio-btn"
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={disabled}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                padding: '10px 20px',
                borderRadius: 999,
                fontSize: 13,
                fontWeight: 500,
                cursor: disabled ? 'not-allowed' : 'pointer',
                opacity: disabled ? 0.5 : 1,
                border: '1.5px dashed #1A73E8',
                background: 'rgba(26,115,232,0.06)',
                color: '#1A73E8',
                transition: 'all 0.15s ease',
                width: '100%',
                justifyContent: 'center',
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLButtonElement).style.background = 'rgba(26,115,232,0.12)'
                ;(e.currentTarget as HTMLButtonElement).style.borderStyle = 'solid'
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLButtonElement).style.background = 'rgba(26,115,232,0.06)'
                ;(e.currentTarget as HTMLButtonElement).style.borderStyle = 'dashed'
              }}
            >
              <UploadIcon />
              Upload an audio file
            </button>
          )}
        </div>
      )}

      {/* ── Preview Panel ── */}
      {isPreview && previewBlob && (
        <div className="w-full flex flex-col gap-4 animate-fade-up">
          <div className="flex items-center justify-center gap-2">
            <span className="nb-dot" />
            <span className="text-xs font-semibold nb-label" style={{ color: '#34A853' }}>
              {uploadedFileName ? 'Audio File Ready' : 'Recording Complete'}
            </span>
          </div>

          <AudioPreview blob={previewBlob} durationMs={previewDuration} />

          <div className="flex items-center gap-2 w-full">
            <button
              id="voice-submit-btn"
              type="button"
              onClick={handleSubmit}
              className="flex-1 nb-btn-primary justify-center py-3 rounded-xl"
            >
              <SendIcon />
              Ask This Question
            </button>
            <button
              id="voice-rerecord-btn"
              type="button"
              onClick={handleReRecord}
              className="nb-btn-ghost py-3 px-4 rounded-xl"
              title="Discard and re-record"
            >
              <RetryIcon />
              Re-record
            </button>
          </div>
        </div>
      )}

      {/* ── Transcribing ── */}
      {isTranscribing && (
        <div className="w-full flex items-center justify-center gap-3 py-3 animate-fade-up">
          <div className="w-4 h-4 rounded-full border-2 border-sand-300 border-t-blue-500 animate-spin flex-shrink-0" />
          <span className="text-sm font-medium text-ink-muted">Transcribing your question…</span>
        </div>
      )}
    </div>
  )
}
