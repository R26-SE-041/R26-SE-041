'use client'

/**
 * useVoiceRecorder — MediaRecorder hook.
 *
 * Exposes:
 *   - recordingState, audioBlob, durationMs — existing API
 *   - frequencyBins: number[]  — real-time per-bin amplitude (0–1), 32 bins
 *     Updated ~30fps via requestAnimationFrame.  Use this to draw a live waveform.
 *   - audioLevel: number — scalar 0–1 (average of bins, kept for compat)
 */

import { useCallback, useRef, useState } from 'react'
import type { RecordingState } from '@/types'

const NUM_BINS = 32   // number of frequency bars exposed to the UI

interface UseVoiceRecorderReturn {
  recordingState: RecordingState
  audioBlob: Blob | null
  audioLevel: number          // 0–1 scalar (average)
  frequencyBins: number[]     // 0–1 per-bin amplitude, length = NUM_BINS
  startRecording: () => Promise<void>
  stopRecording: () => void
  clearRecording: () => void
  durationMs: number
}

export function useVoiceRecorder(): UseVoiceRecorderReturn {
  const [recordingState, setRecordingState] = useState<RecordingState>('idle')
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null)
  const [audioLevel, setAudioLevel] = useState(0)
  const [frequencyBins, setFrequencyBins] = useState<number[]>(Array(NUM_BINS).fill(0))
  const [durationMs, setDurationMs] = useState(0)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const analyserRef = useRef<AnalyserNode | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)   // track context so we can close it
  const animFrameRef = useRef<number>(0)
  const startTimeRef = useRef<number>(0)
  const streamRef = useRef<MediaStream | null>(null)
  const dataArrayRef = useRef<Uint8Array | null>(null)

  const stopLevelTracking = useCallback(() => {
    cancelAnimationFrame(animFrameRef.current)
    setAudioLevel(0)
    setFrequencyBins(Array(NUM_BINS).fill(0))
  }, [])

  const trackAudioLevel = useCallback((analyser: AnalyserNode) => {
    // Use frequencyBinCount from the analyser (fftSize / 2)
    const rawData = new Uint8Array(analyser.frequencyBinCount)
    dataArrayRef.current = rawData

    const tick = () => {
      analyser.getByteFrequencyData(rawData)

      // Downsample raw FFT bins → NUM_BINS display bins
      const step = Math.floor(rawData.length / NUM_BINS)
      const bins: number[] = []
      for (let i = 0; i < NUM_BINS; i++) {
        // Average a block of FFT bins for each display bar
        let sum = 0
        for (let j = 0; j < step; j++) {
          sum += rawData[i * step + j]
        }
        bins.push(Math.min((sum / step) / 255, 1))   // normalise 0–1
      }

      // Scalar level = mean of all bins
      const avg = bins.reduce((a, b) => a + b, 0) / bins.length

      setFrequencyBins(bins)
      setAudioLevel(avg)
      animFrameRef.current = requestAnimationFrame(tick)
    }
    animFrameRef.current = requestAnimationFrame(tick)
  }, [])

  const startRecording = useCallback(async () => {
    try {
      // DO NOT force sampleRate: 16000 here — browsers treat it as a hint and
      // often produce corrupted/distorted audio when they try to honour it.
      // The backend (torchaudio + ffmpeg) already resamples cleanly from the
      // browser's native rate (typically 48 kHz) down to 16 kHz.
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,        // Mono — models process mono internally
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,  // Stabilise mic volume across recordings
        },
      })
      streamRef.current = stream

      // AudioContext for the live frequency analyser only — NOT used for recording.
      // Do NOT force sampleRate here: getSettings().sampleRate is unreliable across
      // browsers (Safari/Firefox often return undefined) and mismatched rates cause
      // the browser to silently reject or corrupt the AudioContext.
      // Close any leftover context from a previous session first.
      if (audioCtxRef.current) {
        audioCtxRef.current.close().catch(() => {})
        audioCtxRef.current = null
      }
      const ctx = new AudioContext()
      audioCtxRef.current = ctx
      const source = ctx.createMediaStreamSource(stream)
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 256
      analyser.smoothingTimeConstant = 0.6
      source.connect(analyser)
      analyserRef.current = analyser
      trackAudioLevel(analyser)

      // Pick the best supported container.  webm/opus gives smallest files;
      // mp4/aac is the Safari fallback; raw wav is the last resort.
      const mimeType = (
        MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' :
        MediaRecorder.isTypeSupported('audio/mp4')              ? 'audio/mp4'              :
                                                                  'audio/wav'
      )

      // timeslice=250 ms: flush chunks every 250 ms so Firefox doesn't lose
      // the last chunk on stop() when no timeslice is set.
      const recorder = new MediaRecorder(stream, { mimeType })
      chunksRef.current = []

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      recorder.onstop = () => {
        // Stop the mic stream tracks immediately so the browser releases the mic.
        streamRef.current?.getTracks().forEach((t) => t.stop())
        stopLevelTracking()

        // IMPORTANT: wrap Blob creation in setTimeout(0) so that any final
        // ondataavailable event (the last chunk emitted on stop()) has a chance
        // to fire and push into chunksRef before we assemble the Blob.
        // Without this, browsers may deliver the final chunk AFTER onstop fires,
        // causing the last 250 ms of audio to be silently dropped.
        const recordedDuration = Date.now() - startTimeRef.current
        setTimeout(() => {
          const blob = new Blob(chunksRef.current, { type: mimeType })
          setAudioBlob(blob)
          setDurationMs(recordedDuration)
          // Close the AudioContext now that the session is fully done.
          audioCtxRef.current?.close().catch(() => {})
          audioCtxRef.current = null
          setRecordingState('done')
        }, 0)
      }

      recorder.start(250) // 250 ms timeslice — progressive chunks, no last-ms cutoff
      mediaRecorderRef.current = recorder
      startTimeRef.current = Date.now()
      setRecordingState('recording')
    } catch (err) {
      console.error('Microphone access denied:', err)
      setRecordingState('error')
    }
  }, [trackAudioLevel, stopLevelTracking])

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop()
      setRecordingState('processing')
    }
  }, [])

  const clearRecording = useCallback(() => {
    setAudioBlob(null)
    setDurationMs(0)
    setFrequencyBins(Array(NUM_BINS).fill(0))
    setRecordingState('idle')
  }, [])

  return {
    recordingState,
    audioBlob,
    audioLevel,
    frequencyBins,
    startRecording,
    stopRecording,
    clearRecording,
    durationMs,
  }
}
