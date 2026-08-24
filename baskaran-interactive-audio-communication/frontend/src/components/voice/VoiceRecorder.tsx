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

/* ── Live Frequency Waveform ── */
function LiveWaveform({ bins, active }: { bins: number[]; active: boolean }) {
  return (
    <div className="flex items-end justify-center gap-[3px]" style={{ height: 48 }} aria-hidden>
      {bins.map((amplitude, i) => {
        // Idle: gentle breathing animation using a sine wave per bar
        // Active: actual microphone amplitude per frequency bin
        const pct = active
          ? Math.max(4, amplitude * 100)
          : 8 + Math.sin(i * 0.6) * 4  // subtle idle shimmer
        return (
          <div
            key={i}
            className={[
              'rounded-full transition-all',
              active
                ? 'bg-gradient-to-t from-violet-500 via-purple-400 to-indigo-300'
                : 'bg-white/20',
            ].join(' ')}
            style={{
              width: 4,
              height: `${pct}%`,
              // Stagger animation delay so idle state gently ripples
              transitionDuration: active ? '60ms' : '600ms',
              animationDelay: `${i * 0.04}s`,
            }}
          />
        )
      })}
    </div>
  )
}

/* ── Mic SVG ── */
function MicIcon() {
  return (
    <svg width="30" height="30" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="22" />
      <line x1="9"  y1="22" x2="15" y2="22" />
    </svg>
  )
}

/* ── Stop square ── */
function StopIcon() {
  return <div className="w-6 h-6 rounded-md bg-white shadow-sm" />
}

/* ── Spinner ── */
function Spinner() {
  return <div className="w-7 h-7 rounded-full border-[2.5px] border-white/25 border-t-white animate-spin" />
}

/* ── Play icon ── */
function PlayIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
      <polygon points="5 3 19 12 5 21 5 3" />
    </svg>
  )
}

/* ── Pause icon ── */
function PauseIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
      <rect x="6" y="4" width="4" height="16" rx="1" />
      <rect x="14" y="4" width="4" height="16" rx="1" />
    </svg>
  )
}

/* ── Send icon ── */
function SendIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  )
}

/* ── Re-record icon ── */
function RetryIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <polyline points="1 4 1 10 7 10" />
      <path d="M3.51 15a9 9 0 1 0 .49-3.87" />
    </svg>
  )
}

/* ── Audio Preview Player ── */
function AudioPreview({ blob, durationMs }: { blob: Blob; durationMs: number }) {
  const audioRef = useRef<HTMLAudioElement>(null)
  const [playing, setPlaying] = useState(false)
  const [progress, setProgress] = useState(0)
  const [currentTime, setCurrentTime] = useState(0)
  const urlRef = useRef<string>('')

  useEffect(() => {
    const url = URL.createObjectURL(blob)
    urlRef.current = url
    if (audioRef.current) {
      audioRef.current.src = url
      audioRef.current.load()   // Fix 2: must call load() after setting src
    }
    return () => URL.revokeObjectURL(url)
  }, [blob])

  const togglePlay = () => {
    const el = audioRef.current
    if (!el) return
    if (playing) {
      el.pause()
    } else {
      el.play()
    }
  }

  const handleTimeUpdate = () => {
    const el = audioRef.current
    if (!el) return
    // Fix 3: webm/opus often reports duration as Infinity — fall back to prop
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
    const x = e.clientX - rect.left
    const ratio = Math.max(0, Math.min(1, x / rect.width))
    el.currentTime = ratio * dur
    setProgress(ratio * 100)
  }

  const fmt = (s: number) =>
    `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(Math.floor(s % 60)).padStart(2, '0')}`

  // Fix 3: webm duration can be Infinity — use prop fallback
  const totalSec = durationMs / 1000

  return (
    <div className="w-full flex flex-col gap-2.5 bg-emerald-500/8 border border-emerald-500/25 rounded-2xl px-4 py-3.5">
      <audio
        ref={audioRef}
        preload="metadata"
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => { setPlaying(false); setProgress(100) }}
        onTimeUpdate={handleTimeUpdate}
      />

      <div className="flex items-center gap-3">
        {/* Play / Pause button */}
        <button
          id="audio-preview-play-btn"
          type="button"
          onClick={togglePlay}
          className="w-10 h-10 rounded-full bg-emerald-500/20 hover:bg-emerald-500/35 border border-emerald-500/30 flex items-center justify-center text-emerald-300 transition-all hover:scale-105 active:scale-95 shrink-0"
          aria-label={playing ? 'Pause preview' : 'Play preview'}
        >
          {playing ? <PauseIcon /> : <PlayIcon />}
        </button>

        {/* Progress bar + time */}
        <div className="flex-1 flex flex-col gap-1.5">
          <div
            className="w-full h-1.5 bg-white/10 rounded-full cursor-pointer relative overflow-hidden"
            onClick={handleSeek}
            role="slider"
            aria-label="Audio progress"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(progress)}
          >
            <div
              className="h-full bg-gradient-to-r from-emerald-400 to-emerald-300 rounded-full transition-all duration-100"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="flex justify-between text-[10px] font-mono text-white/30">
            <span>{fmt(currentTime)}</span>
            <span>{fmt(totalSec)}</span>
          </div>
        </div>
      </div>

      <p className="text-[11px] text-emerald-400/70 font-medium flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
        Recording ready — listen before submitting
      </p>
    </div>
  )
}

/* ── Main ── */
export function VoiceRecorder({ language, onTranscript, onError, disabled = false }: VoiceRecorderProps) {
  const { recordingState, audioBlob, audioLevel, frequencyBins, durationMs, startRecording, stopRecording, clearRecording } = useVoiceRecorder()
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

  /* When recording finishes → show preview instead of auto-sending */
  useEffect(() => {
    if (recordingState === 'done' && audioBlob) {
      setPreviewBlob(audioBlob)
      setPreviewDuration(durationMs)
      setUploadedFileName(null)
    }
  }, [recordingState, audioBlob, durationMs])

  /* Submit — user approved the recording */
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

  /* Re-record — discard preview */
  const handleReRecord = useCallback(() => {
    setPreviewBlob(null)
    setPreviewDuration(0)
    setUploadedFileName(null)
    clearRecording()
  }, [clearRecording])

  /* Local audio upload uses the same STT endpoint as microphone recordings. */
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
  // Show preview state when blob is ready
  const isPreview    = !!(previewBlob && !isTranscribing)
  const btnDisabled  = disabled || isProcessing || isTranscribing || isPreview

  const fmt = (s: number) =>
    `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`

  return (
    <div className="flex flex-col items-center gap-6 w-full py-4">
      <input
        ref={fileInputRef}
        type="file"
        accept="audio/wav,audio/x-wav,audio/mpeg,audio/mp3,audio/mp4,audio/m4a,audio/x-m4a,audio/webm,audio/ogg,.wav,.mp3,.m4a,.webm,.ogg"
        onChange={handleAudioUpload}
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
      />

      {/* ── Mic button (hidden during preview) ── */}
      {!isPreview && (
        <>
          {/* ── Mic button ── */}
          <div className="relative flex items-center justify-center" style={{ width: 160, height: 160 }}>
            {/* Ping rings — recording only */}
            {isRecording && (
              <>
                <span className="absolute rounded-full border border-red-500/35 animate-ping" style={{ inset: '20px' }} />
                <span className="absolute rounded-full border border-red-500/20 animate-ping [animation-delay:0.5s]" style={{ inset: '8px' }} />
              </>
            )}

            {/* Idle ambient glow */}
            {!isRecording && !isProcessing && !isTranscribing && (
              <span className="absolute rounded-full bg-brand-500/12 animate-pulse-slow" style={{ inset: '20px' }} />
            )}

            <button
              id="voice-record-btn"
              type="button"
              aria-label={isRecording ? 'Stop recording' : 'Start recording'}
              onClick={toggle}
              disabled={btnDisabled}
              className={clsx(
                'relative z-10 w-24 h-24 rounded-full flex items-center justify-center transition-all duration-250',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-4 focus-visible:ring-offset-surface-900',
                'disabled:opacity-50 disabled:pointer-events-none',
                isRecording
                  ? 'bg-gradient-to-br from-red-500 to-rose-600 scale-105 shadow-red focus-visible:ring-red-500'
                  : 'bg-brand-gradient scale-100 hover:scale-[1.04] active:scale-[0.97] shadow-brand focus-visible:ring-brand-500'
              )}
            >
              {(isProcessing || isTranscribing) ? <Spinner /> : isRecording ? <StopIcon /> : <MicIcon />}
            </button>
          </div>

          {!isRecording && !isProcessing && !isTranscribing && (
            <button
              id="voice-upload-audio-btn"
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={disabled}
              className="text-xs font-medium text-white/45 hover:text-brand-300 transition-colors disabled:opacity-50"
            >
              Upload an audio file
            </button>
          )}

          {/* ── Live Waveform + Status ── */}
          <div className="flex flex-col items-center gap-3 w-full">

            {/* Waveform — always visible, reacts to voice when recording */}
            <div className={clsx(
              'w-full rounded-2xl px-4 py-3 transition-all duration-300',
              isRecording
                ? 'bg-violet-500/10 border border-violet-500/25'
                : 'bg-white/[0.02] border border-white/[0.05]'
            )}>
              <LiveWaveform bins={frequencyBins} active={isRecording} />
            </div>

            {/* Status text */}
            {isRecording ? (
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-red-400 animate-pulse" />
                <span className="text-[12px] font-semibold text-red-400 tracking-wide">Recording — speak now</span>
              </div>
            ) : (isProcessing || isTranscribing) ? (
              <p className="text-[13px] font-medium text-brand-400 animate-pulse">
                {isTranscribing
                  ? 'Transcribing your question…'
                  : 'Processing…'}
              </p>
            ) : (
              <p className="text-[12px] font-medium text-white/35">
                Tap to speak
              </p>
            )}

            {/* Timer */}
            {isRecording && (
              <span className="inline-flex items-center gap-1.5 bg-red-500/10 border border-red-500/20 rounded-full px-3 py-1">
                <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" />
                <span className="text-xs font-mono font-semibold text-red-400 tracking-widest">{fmt(elapsed)}</span>
              </span>
            )}
          </div>
        </>
      )}

      {/* ── Preview Panel ── */}
      {isPreview && previewBlob && (
        <div className="w-full flex flex-col gap-4 animate-fade-up">
          {/* Header */}
          <div className="flex items-center justify-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-[11px] font-bold uppercase tracking-[0.12em] text-emerald-400/80">
              {uploadedFileName ? 'Audio File Ready' : 'Recording Ready'}
            </span>
          </div>

          {/* Audio player */}
          <AudioPreview blob={previewBlob} durationMs={previewDuration} />

          {/* Actions */}
          <div className="flex items-center gap-3 w-full">
            {/* Submit */}
            <button
              id="voice-submit-btn"
              type="button"
              onClick={handleSubmit}
              className="flex-1 inline-flex items-center justify-center gap-2 bg-gradient-to-r from-brand-600 to-accent-600 hover:from-brand-500 hover:to-accent-500 text-white text-sm font-semibold px-5 py-3 rounded-xl transition-all shadow-brand hover:scale-[1.02] active:scale-[0.98]"
            >
              <SendIcon />
              Ask This Question
            </button>

            {/* Re-record */}
            <button
              id="voice-rerecord-btn"
              type="button"
              onClick={handleReRecord}
              className="inline-flex items-center gap-2 bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 text-white/50 hover:text-white/80 text-sm font-medium px-4 py-3 rounded-xl transition-all"
              title="Discard and re-record"
            >
              <RetryIcon />
              Re-record
            </button>
          </div>
        </div>
      )}

      {/* ── Transcribing spinner (full-width) ── */}
      {isTranscribing && (
        <div className="w-full flex items-center justify-center gap-3 py-4 animate-fade-up">
          <div className="w-5 h-5 rounded-full border-2 border-brand-500/30 border-t-brand-400 animate-spin shrink-0" />
          <span className="text-sm text-brand-400 animate-pulse font-medium">
            Transcribing your question…
          </span>
        </div>
      )}

    </div>
  )
}
