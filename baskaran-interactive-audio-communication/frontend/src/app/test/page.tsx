'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import { LanguageSelector } from '@/components/voice/LanguageSelector'
import { VoiceRecorder } from '@/components/voice/VoiceRecorder'
import type { Language, TranscribeResponse, DocumentItem, AskResponse } from '@/types'
import { uploadDocument, listDocuments, deleteDocument, correctTranscript, askDocument, synthesizeTamilSpeech, testSynthesizeTamilSpeech, synthesizeEnglishSpeech, testSynthesizeEnglishSpeech, synthesizeMixedSpeech, testSynthesizeMixedSpeech, testSynthesizeMultilingualSpeech, testSynthesizeIndicParlerMixedSpeech, testSynthesizeSinhalaSpeech, testSinhalaRomanize, testSinhalaPhoneticPreview, testSinhalaASR, type SinhalaPhoneticPreview } from '@/lib/api'
import type { MixedTTSSegment } from '@/lib/api'

// ── TEMPORARY feature flags (read once at module level, never re-read per render) ─
// NEXT_PUBLIC_USE_TAMIL_TTS: when false, disables the existing RAG→TTS auto-trigger
//   so only the manual test textarea calls Tamil TTS during the test period.
// NEXT_PUBLIC_USE_TAMIL_TTS_TEST: when true, shows the isolated TTS test section.
// REMOVE these constants after TTS testing is complete.
const _USE_TAMIL_TTS      = process.env.NEXT_PUBLIC_USE_TAMIL_TTS      !== 'false'
const _USE_TAMIL_TTS_TEST = process.env.NEXT_PUBLIC_USE_TAMIL_TTS_TEST === 'true'

// ── English TTS feature flags ───────────────────────────────────────────────
// NEXT_PUBLIC_USE_ENGLISH_TTS: when false, disables RAG→TTS auto-trigger for English.
// NEXT_PUBLIC_USE_ENGLISH_TTS_TEST: when true, shows the isolated English TTS test section.
const _USE_ENGLISH_TTS      = process.env.NEXT_PUBLIC_USE_ENGLISH_TTS      !== 'false'
const _USE_ENGLISH_TTS_TEST = process.env.NEXT_PUBLIC_USE_ENGLISH_TTS_TEST === 'true'

// ── Mixed TTS feature flags ─────────────────────────────────────────────────
// NEXT_PUBLIC_USE_MIXED_TTS: when true, Tamil-mode answers with mixed script
//   (Tamil + Latin) are routed to the orchestrator instead of pure IndicF5.
// NEXT_PUBLIC_USE_MIXED_TTS_TEST: when true, shows the isolated mixed TTS test
//   section (segment preview + Generate Audio button).
const _USE_MIXED_TTS      = process.env.NEXT_PUBLIC_USE_MIXED_TTS      !== 'false'
const _USE_MIXED_TTS_TEST = process.env.NEXT_PUBLIC_USE_MIXED_TTS_TEST === 'true'

// ── Mode C — Multilingual Single-Model TTS feature flag ─────────────────────
// Shows/hides the isolated Mode C test panel.
// Mode C sends the ORIGINAL mixed text with NO pre-processing to ONE IndicF5 call.
// REMOVE this constant after Mode C evaluation is complete.
const _USE_MULTILINGUAL_TTS_TEST = process.env.NEXT_PUBLIC_USE_MULTILINGUAL_TTS_TEST === 'true'

// ── Mode D — Indic Parler Mixed TTS feature flag ──────────────────────────────
// Shows/hides the isolated Mode D test panel.
// Mode D uses ai4bharat/indic-parler-tts — a NEW unified multilingual model.
// NOT IndicF5. NOT Parler-TTS Mini v1. Completely isolated from all existing TTS.
// REMOVE this constant after Mode D evaluation is complete.
const _USE_INDIC_PARLER_MIXED_TTS_TEST = process.env.NEXT_PUBLIC_USE_INDIC_PARLER_MIXED_TTS_TEST === 'true'

// ── Sinhala TTS Test feature flag ────────────────────────────────────────────
// Shows/hides the isolated Sinhala TTS test panel.
// Uses dialoglk/SinhalaVITS-TTS-F1 (Nipunika female, Coqui VITS, 22,050 Hz).
// Completely isolated — does NOT affect Tamil/English/Mixed TTS or RAG.
// REMOVE this constant after Sinhala TTS evaluation is complete.
const _USE_SINHALA_TTS_TEST = process.env.NEXT_PUBLIC_USE_SINHALA_TTS_TEST === 'true'

// ── Sinhala ASR Test feature flag ─────────────────────────────────────────────
// Shows/hides the isolated Sinhala ASR test panel.
// Uses Lingalingeswaran/whisper-small-sinhala (fine-tuned openai/whisper-small).
// File-upload only — does NOT use useVoiceRecorder or affect Tamil/English ASR.
// REMOVE this constant after Sinhala ASR evaluation is complete.
const _USE_SINHALA_ASR_TEST = process.env.NEXT_PUBLIC_USE_SINHALA_ASR_TEST === 'true'

// ── Script detection utility (mirrors backend detect_script) ─────────────────
// Used to decide whether to call synthesizeMixedSpeech or synthesizeTamilSpeech
// without a round-trip to the backend for classification.
function _detectScript(text: string): 'tamil' | 'english' | 'mixed' {
  let tamil = 0, latin = 0
  for (const ch of text) {
    const cp = ch.codePointAt(0) ?? 0
    if (cp >= 0x0B80 && cp <= 0x0BFF) tamil++
    else if ((cp >= 0x41 && cp <= 0x5A) || (cp >= 0x61 && cp <= 0x7A)) latin++
  }
  const total = tamil + latin
  if (total === 0) return 'english'
  if (tamil / total >= 0.90) return 'tamil'
  if (latin / total >= 0.90) return 'english'
  return 'mixed'
}

// ─────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────

type AppPhase =
  | 'idle'              // waiting for recording
  | 'transcript'        // STT done — show raw transcript + action buttons
  | 'correcting'        // calling /documents/correct-transcript via Gemma 4 12B
  | 'corrected'         // show corrected transcript for user to review/edit
  | 'asking'            // calling /documents/ask with chosen query
  | 'answered'          // answer ready

interface QAResult {
  transcript: string
  corrected_transcript: string
  answer: string
  references: AskResponse['references']
}

// ─────────────────────────────────────────────
// Main Page
// ─────────────────────────────────────────────

export default function StudyAssistantPage() {
  // ── Language
  const [language, setLanguage] = useState<Language>('english')

  // ── Documents
  const [docs, setDocs] = useState<DocumentItem[]>([])
  const [docsLoaded, setDocsLoaded] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)
  const [docPanelOpen, setDocPanelOpen] = useState(false)

  // ── Voice / QA
  const [phase, setPhase] = useState<AppPhase>('idle')
  const [sttResult, setSttResult] = useState<TranscribeResponse | null>(null)
  const [voiceError, setVoiceError] = useState<string | null>(null)

  // ── Transcript Correction
  const [correctedTranscriptText, setCorrectedTranscriptText] = useState('')
  const [correctError, setCorrectError] = useState<string | null>(null)

  // ── Answer
  const [qaResult, setQaResult] = useState<QAResult | null>(null)
  const [askError, setAskError] = useState<string | null>(null)
  const answerRef = useRef<HTMLDivElement>(null)

  // ── Tamil TTS (Tamil-only; Sinhala/English untouched)
  const [tamilAudioUrl, setTamilAudioUrl] = useState<string | null>(null)
  const [tamilAudioLoading, setTamilAudioLoading] = useState(false)
  const [tamilAudioError, setTamilAudioError] = useState<string | null>(null)
  const [tamilAudioPlaying, setTamilAudioPlaying] = useState(false)
  const tamilAudioRef = useRef<HTMLAudioElement>(null)

  // TEMPORARY RAG TEST PATH: independent of the voice/ASR state machine.
  const [typedQuestion, setTypedQuestion] = useState('')
  const [typedAsking, setTypedAsking] = useState(false)
  const [typedResult, setTypedResult] = useState<QAResult | null>(null)
  const [typedAskError, setTypedAskError] = useState<string | null>(null)

  // ── TEMPORARY TTS Test state (completely isolated from ASR/RAG) ───────────
  const [ttsTestText, setTtsTestText] = useState('')
  const [ttsTestEngine, setTtsTestEngine] = useState<'indic-parler' | 'mms'>('indic-parler')
  const [ttsTestLoading, setTtsTestLoading] = useState(false)
  const [ttsTestAudioUrl, setTtsTestAudioUrl] = useState<string | null>(null)
  const [ttsTestPlaying, setTtsTestPlaying] = useState(false)
  const [ttsTestError, setTtsTestError] = useState<string | null>(null)
  const ttsTestAudioRef = useRef<HTMLAudioElement>(null)
  const ttsTestRequestIdRef = useRef<number>(0)
  // ── END TEMPORARY TTS Test state ─────────────────────────────────────────

  // ── TEMPORARY English TTS Test state (isolated from ASR/RAG) ──────────────
  // REMOVE this block after English TTS testing is complete.
  const [englishTtsTestText, setEnglishTtsTestText] = useState('')
  const [englishTtsTestDescription, setEnglishTtsTestDescription] = useState('')
  const [englishTtsTestLoading, setEnglishTtsTestLoading] = useState(false)
  const [englishTtsTestAudioUrl, setEnglishTtsTestAudioUrl] = useState<string | null>(null)
  const [englishTtsTestPlaying, setEnglishTtsTestPlaying] = useState(false)
  const [englishTtsTestError, setEnglishTtsTestError] = useState<string | null>(null)
  const englishTtsTestAudioRef = useRef<HTMLAudioElement>(null)
  const englishTtsTestRequestIdRef = useRef<number>(0)
  // -- END TEMPORARY English TTS Test state ----------------------------------

  // -- TEMPORARY Mixed TTS Test state (isolated from ASR/RAG) ----------------
  // REMOVE this block after mixed TTS testing is complete.
  const [mixedTtsTestText, setMixedTtsTestText]         = useState('')
  const [mixedTtsTestLoading, setMixedTtsTestLoading]   = useState(false)
  const [mixedTtsTestAudioUrl, setMixedTtsTestAudioUrl] = useState<string | null>(null)
  const [mixedTtsTestPlaying, setMixedTtsTestPlaying]   = useState(false)
  const [mixedTtsTestError, setMixedTtsTestError]       = useState<string | null>(null)
  const [mixedTtsTestSegments, setMixedTtsTestSegments] = useState<MixedTTSSegment[] | null>(null)
  const [mixedTtsTestMode, setMixedTtsTestMode] = useState<'a' | 'b'>('a')
  const [mixedTtsNormalizedText, setMixedTtsNormalizedText] = useState<string | null>(null)
  const [mixedTtsModeUsed, setMixedTtsModeUsed] = useState<string | null>(null)
  const [mixedTtsVoiceMatching, setMixedTtsVoiceMatching] = useState(true)
  const mixedTtsTestAudioRef     = useRef<HTMLAudioElement>(null)
  const mixedTtsTestRequestIdRef = useRef<number>(0)
  // -- END TEMPORARY Mixed TTS Test state ------------------------------------

  // -- TEMPORARY Mode C Multilingual TTS Test state --------------------------
  const [multilingualTtsTestText, setMultilingualTtsTestText]         = useState('')
  const [multilingualTtsTestLoading, setMultilingualTtsTestLoading]   = useState(false)
  const [multilingualTtsTestAudioUrl, setMultilingualTtsTestAudioUrl] = useState<string | null>(null)
  const [multilingualTtsTestPlaying, setMultilingualTtsTestPlaying]   = useState(false)
  const [multilingualTtsTestError, setMultilingualTtsTestError]       = useState<string | null>(null)
  const [multilingualTtsLatencyMs, setMultilingualTtsLatencyMs]       = useState<number | null>(null)
  const multilingualTtsTestAudioRef     = useRef<HTMLAudioElement>(null)
  const multilingualTtsTestRequestIdRef = useRef<number>(0)
  // -- END TEMPORARY Mode C Multilingual TTS Test state ----------------------

  // -- TEMPORARY Mode D Indic Parler Mixed TTS Test state --------------------
  const [indicParlerMixedText, setIndicParlerMixedText]         = useState('')
  const [indicParlerMixedLoading, setIndicParlerMixedLoading]   = useState(false)
  const [indicParlerMixedAudioUrl, setIndicParlerMixedAudioUrl] = useState<string | null>(null)
  const [indicParlerMixedPlaying, setIndicParlerMixedPlaying]   = useState(false)
  const [indicParlerMixedError, setIndicParlerMixedError]       = useState<string | null>(null)
  const [indicParlerMixedLatencyMs, setIndicParlerMixedLatencyMs] = useState<number | null>(null)
  const [indicParlerMixedSampleRate, setIndicParlerMixedSampleRate] = useState<number | null>(null)
  const [indicParlerMixedSpeaker, setIndicParlerMixedSpeaker]   = useState<string | null>(null)
  const indicParlerMixedAudioRef     = useRef<HTMLAudioElement>(null)
  const indicParlerMixedRequestIdRef = useRef<number>(0)
  // -- END TEMPORARY Mode D Indic Parler Mixed TTS Test state ----------------

  // TEMPORARY Sinhala VITS TTS Test state
  const [sinhalaTtsText, setSinhalaTtsText]             = useState('')
  const [sinhalaTtsLoading, setSinhalaTtsLoading]       = useState(false)
  const [sinhalaTtsAudioUrl, setSinhalaTtsAudioUrl]     = useState<string | null>(null)
  const [sinhalaTtsPlaying, setSinhalaTtsPlaying]       = useState(false)
  const [sinhalaTtsError, setSinhalaTtsError]           = useState<string | null>(null)
  const [sinhalaTtsLatencyMs, setSinhalaTtsLatencyMs]   = useState<number | null>(null)
  const [sinhalaTtsSampleRate, setSinhalaTtsSampleRate] = useState<number | null>(null)
  const [sinhalaRomanized, setSinhalaRomanized]         = useState<string | null>(null)
  const [sinhalaRomanizeLoading, setSinhalaRomanizeLoading] = useState(false)
  const [sinhalaMixedPhonetics, setSinhalaMixedPhonetics] = useState(false)
  const [sinhalaPhoneticPreview, setSinhalaPhoneticPreview] = useState<SinhalaPhoneticPreview | null>(null)
  const sinhalaTtsAudioRef     = useRef<HTMLAudioElement>(null)
  const sinhalaTtsRequestIdRef = useRef<number>(0)
  // END TEMPORARY Sinhala VITS TTS Test state

  // TEMPORARY Sinhala ASR Test state (file-upload only, isolated from useVoiceRecorder)
  // REMOVE this block after Sinhala ASR evaluation is complete.
  const [sinhalaAsrFile, setSinhalaAsrFile]             = useState<File | null>(null)
  const [sinhalaAsrLoading, setSinhalaAsrLoading]       = useState(false)
  const [sinhalaAsrTranscript, setSinhalaAsrTranscript] = useState<string | null>(null)
  const [sinhalaAsrError, setSinhalaAsrError]           = useState<string | null>(null)
  const [sinhalaAsrLatencyMs, setSinhalaAsrLatencyMs]   = useState<number | null>(null)
  const [sinhalaAsrElapsed, setSinhalaAsrElapsed]       = useState(0)
  const sinhalaAsrFileInputRef = useRef<HTMLInputElement>(null)
  const sinhalaAsrTimerRef     = useRef<ReturnType<typeof setInterval> | null>(null)
  // END TEMPORARY Sinhala ASR Test state

  // English TTS production state
  const [englishAudioUrl, setEnglishAudioUrl] = useState<string | null>(null)
  const [englishAudioLoading, setEnglishAudioLoading] = useState(false)
  const [englishAudioError, setEnglishAudioError] = useState<string | null>(null)
  const [englishAudioPlaying, setEnglishAudioPlaying] = useState(false)
  const englishAudioRef = useRef<HTMLAudioElement>(null)

  const lastSynthesizedTamilRef   = useRef<string | null>(null)
  const lastSynthesizedEnglishRef = useRef<string | null>(null)

  useEffect(() => {
    if (phase === 'answered' || typedResult) {
      answerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [phase, typedResult])

  useEffect(() => { return () => { setTtsTestAudioUrl((p) => { if (p) URL.revokeObjectURL(p); return null }) } }, [])
  useEffect(() => { return () => { setEnglishTtsTestAudioUrl((p) => { if (p) URL.revokeObjectURL(p); return null }) } }, [])
  useEffect(() => { return () => { setMixedTtsTestAudioUrl((p) => { if (p) URL.revokeObjectURL(p); return null }) } }, [])
  useEffect(() => { return () => { setMultilingualTtsTestAudioUrl((p) => { if (p) URL.revokeObjectURL(p); return null }) } }, [])
  useEffect(() => { return () => { setSinhalaTtsAudioUrl((p) => { if (p) URL.revokeObjectURL(p); return null }) } }, [])

  const displayedAnswerText = (qaResult ?? typedResult)?.answer ?? null
  useEffect(() => {
    if (!_USE_ENGLISH_TTS) return
    if (language !== 'english') return
    if (!displayedAnswerText) return
    const synthesisKey = `english::${displayedAnswerText}`
    if (lastSynthesizedEnglishRef.current === synthesisKey) return
    lastSynthesizedEnglishRef.current = synthesisKey
    if (englishAudioUrl) { URL.revokeObjectURL(englishAudioUrl); setEnglishAudioUrl(null) }
    setEnglishAudioError(null); setEnglishAudioPlaying(false); setEnglishAudioLoading(true)
    let cancelled = false
    synthesizeEnglishSpeech(displayedAnswerText)
      .then((blob) => { if (cancelled) return; setEnglishAudioUrl(URL.createObjectURL(blob)); setEnglishAudioLoading(false) })
      .catch((err: Error) => { if (cancelled) return; setEnglishAudioError(err.message ?? 'English audio unavailable'); setEnglishAudioLoading(false) })
    return () => { cancelled = true }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [displayedAnswerText, language])

  // -- Unified Tamil-mode TTS auto-trigger -----------------------------------
  // ONE effect handles both pure-Tamil and mixed-Tamil+English answers.
  // Replaces the old Tamil-only effect to prevent two effects both watching
  // language==='tamil' and firing simultaneously (duplicate effect bug).
  //
  //   pure Tamil answer           -> synthesizeTamilSpeech()  (IndicF5, unchanged)
  //   mixed Tamil+English answer  -> synthesizeMixedSpeech()  (orchestrator)
  //   _USE_MIXED_TTS=false        -> always synthesizeTamilSpeech() (regression safe)
  //
  // Gated by NEXT_PUBLIC_USE_TAMIL_TTS.
  useEffect(() => {
    if (!_USE_TAMIL_TTS) return
    if (language !== 'tamil') return
    if (!displayedAnswerText) return

    const synthesisKey = `tamil::${displayedAnswerText}`
    if (lastSynthesizedTamilRef.current === synthesisKey) return
    lastSynthesizedTamilRef.current = synthesisKey

    // Clean up any previous audio URL
    if (tamilAudioUrl) {
      URL.revokeObjectURL(tamilAudioUrl)
      setTamilAudioUrl(null)
    }
    setTamilAudioError(null)
    setTamilAudioPlaying(false)
    setTamilAudioLoading(true)

    let cancelled = false
    synthesizeTamilSpeech(displayedAnswerText)
      .then((blob) => {
        if (cancelled) return
        const url = URL.createObjectURL(blob)
        setTamilAudioUrl(url)
        setTamilAudioLoading(false)
      })
      .catch((err: Error) => {
        if (cancelled) return
        setTamilAudioError(err.message ?? 'Tamil audio unavailable')
        setTamilAudioLoading(false)
      })

    return () => { cancelled = true }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [displayedAnswerText, language])

  // ─────────────────────────────────────────────
  // Document handlers
  // ─────────────────────────────────────────────

  const fetchDocs = useCallback(async () => {
    try {
      const list = await listDocuments()
      setDocs(list)
    } catch {
      // show empty state
    } finally {
      setDocsLoaded(true)
    }
  }, [])

  const handleFileUpload = useCallback(async (file: File) => {
    setUploading(true)
    setUploadError(null)
    try {
      const uploaded = await uploadDocument(file)
      setDocs((prev) => [{
        document_id: String(uploaded.document_id ?? Date.now()),
        filename: uploaded.filename,
        file_type: uploaded.file_type as DocumentItem['file_type'],
        chunk_count: uploaded.chunk_count,
        uploaded_at: String(uploaded.uploaded_at ?? new Date().toISOString()),
      }, ...prev])
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFileUpload(file)
  }, [handleFileUpload])

  const handleDelete = useCallback(async (docId: string) => {
    try {
      await deleteDocument(docId)
      setDocs((prev) => prev.filter((d) => d.document_id !== docId))
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : 'Delete failed')
    }
  }, [])

  const toggleDocPanel = () => {
    if (!docPanelOpen && !docsLoaded) fetchDocs()
    setDocPanelOpen((v) => !v)
  }

  // ─────────────────────────────────────────────
  // Voice → Transcript
  // ─────────────────────────────────────────────

  const handleTranscript = useCallback((r: TranscribeResponse) => {
    setVoiceError(null)
    setQaResult(null)
    setTypedResult(null)
    setTypedAskError(null)
    setAskError(null)
    setCorrectError(null)
    setCorrectedTranscriptText('')
    setSttResult(r)
    setPhase('transcript')
  }, [])

  const handleVoiceError = useCallback((msg: string) => {
    setVoiceError(msg)
    setPhase('idle')
  }, [])

  // ─────────────────────────────────────────────
  // Step 2 — Correct transcript via Gemma 4 12B
  // ─────────────────────────────────────────────

  const handleCorrect = useCallback(async () => {
    if (!sttResult?.transcript) return
    setPhase('correcting')
    setCorrectError(null)
    try {
      const result = await correctTranscript(
        sttResult.transcript,
        language,
        sttResult.detected_language
      )
      setCorrectedTranscriptText(result.corrected_transcript)
      setPhase('corrected')
    } catch {
      setCorrectedTranscriptText(sttResult.transcript)
      setCorrectError('Transcript corrector is warming up — using your original transcript.')
      setPhase('corrected')
    }
  }, [sttResult, language])

  // ─────────────────────────────────────────────
  // Step 3 — Ask with corrected transcript
  // ─────────────────────────────────────────────

  const handleAsk = useCallback(async () => {
    if (!sttResult?.transcript || !correctedTranscriptText.trim()) return
    setPhase('asking')
    setAskError(null)
    try {
      const result = await askDocument(
        sttResult.transcript,
        language,
        correctedTranscriptText.trim(),   // corrected_transcript → Hybrid RAG
        sttResult.detected_language
      )
      setQaResult({
        transcript: sttResult.transcript,
        corrected_transcript: correctedTranscriptText.trim(),
        answer: result.answer,
        references: result.references,
      })
      setPhase('answered')
    } catch (e) {
      setAskError(e instanceof Error ? e.message : 'Something went wrong')
      setPhase('corrected')
    }
  }, [sttResult, language, correctedTranscriptText])

  // Ask directly — bypass Gemma correction, send raw transcript to RAG
  const handleAskDirect = useCallback(async () => {
    if (!sttResult?.transcript) return
    setPhase('asking')
    setAskError(null)
    try {
      const result = await askDocument(
        sttResult.transcript,
        language,
        undefined,                   // no corrected_transcript → raw transcript used
        sttResult.detected_language
      )
      setQaResult({
        transcript: sttResult.transcript,
        corrected_transcript: sttResult.transcript,   // raw used as-is
        answer: result.answer,
        references: result.references,
      })
      setPhase('answered')
    } catch (e) {
      setAskError(e instanceof Error ? e.message : 'Something went wrong')
      setPhase('transcript')
    }
  }, [sttResult, language])

  const handleTypedAsk = useCallback(async () => {
    const question = typedQuestion.trim()
    if (!question || typedAsking) return

    setTypedAsking(true)
    setTypedAskError(null)
    setQaResult(null)
    try {
      // Same endpoint as "Ask Directly"; ASR and correction are bypassed.
      const result = await askDocument(question, language)
      setTypedResult({
        transcript: question,
        corrected_transcript: question,
        answer: result.answer,
        references: result.references,
      })
    } catch (e) {
      setTypedAskError(e instanceof Error ? e.message : 'Something went wrong')
    } finally {
      setTypedAsking(false)
    }
  }, [typedQuestion, typedAsking, language])

  const handleReset = useCallback(() => {
    setSttResult(null)
    setQaResult(null)
    setAskError(null)
    setVoiceError(null)
    setCorrectedTranscriptText('')
    setCorrectError(null)
    setTypedResult(null)
    setTypedAskError(null)
    setPhase('idle')
    // Clear synthesis guards so the next answer always triggers TTS fresh
    lastSynthesizedTamilRef.current   = null
    lastSynthesizedEnglishRef.current = null
    // Tamil TTS cleanup
    setTamilAudioUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return null
    })
    setTamilAudioLoading(false)
    setTamilAudioError(null)
    setTamilAudioPlaying(false)
    // English TTS cleanup
    setEnglishAudioUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return null
    })
    setEnglishAudioLoading(false)
    setEnglishAudioError(null)
    setEnglishAudioPlaying(false)
  }, [])

  // ── TEMPORARY TTS Test handler ────────────────────────────────────────────
  // REMOVE this handler after TTS testing is complete.
  const handleTtsTestGenerate = useCallback(async () => {
    const text = ttsTestText.trim()
    if (!text || ttsTestLoading) return

    // Bump request ID — any in-flight request with a stale ID will no-op on return.
    const thisId = ++ttsTestRequestIdRef.current

    // Revoke previous blob URL before creating a new one (memory safety).
    setTtsTestAudioUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return null
    })
    setTtsTestLoading(true)
    setTtsTestError(null)
    setTtsTestPlaying(false)

    try {
      const blob = await testSynthesizeTamilSpeech(text, ttsTestEngine)
      // Only update state if this is still the latest request.
      if (thisId !== ttsTestRequestIdRef.current) return
      const url = URL.createObjectURL(blob)
      setTtsTestAudioUrl(url)
    } catch (err: unknown) {
      if (thisId !== ttsTestRequestIdRef.current) return
      setTtsTestError(
        err instanceof Error ? err.message : 'Tamil TTS test failed — check Modal logs.'
      )
    } finally {
      if (thisId === ttsTestRequestIdRef.current) {
        setTtsTestLoading(false)
      }
    }
  }, [ttsTestText, ttsTestEngine, ttsTestLoading])

  const handleTtsTestReset = useCallback(() => {
    ttsTestRequestIdRef.current++   // cancel any in-flight request
    setTtsTestAudioUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return null
    })
    setTtsTestLoading(false)
    setTtsTestPlaying(false)
    setTtsTestError(null)
    setTtsTestText('')
  }, [])
  // ── END TEMPORARY TTS Test handler ────────────────────────────────────────────

  // ── TEMPORARY English TTS Test handler ──────────────────────────────────────
  // REMOVE this handler after English TTS testing is complete.
  const handleEnglishTtsTestGenerate = useCallback(async () => {
    const text = englishTtsTestText.trim()
    if (!text || englishTtsTestLoading) return

    const thisId = ++englishTtsTestRequestIdRef.current

    setEnglishTtsTestAudioUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return null
    })
    setEnglishTtsTestLoading(true)
    setEnglishTtsTestError(null)
    setEnglishTtsTestPlaying(false)

    try {
      const blob = await testSynthesizeEnglishSpeech(
        text,
        englishTtsTestDescription.trim()
      )
      if (thisId !== englishTtsTestRequestIdRef.current) return
      const url = URL.createObjectURL(blob)
      setEnglishTtsTestAudioUrl(url)
    } catch (err: unknown) {
      if (thisId !== englishTtsTestRequestIdRef.current) return
      setEnglishTtsTestError(
        err instanceof Error ? err.message : 'English TTS test failed — check Modal logs.'
      )
    } finally {
      if (thisId === englishTtsTestRequestIdRef.current) {
        setEnglishTtsTestLoading(false)
      }
    }
  }, [englishTtsTestText, englishTtsTestDescription, englishTtsTestLoading])

  const handleEnglishTtsTestReset = useCallback(() => {
    englishTtsTestRequestIdRef.current++
    setEnglishTtsTestAudioUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return null
    })
    setEnglishTtsTestLoading(false)
    setEnglishTtsTestPlaying(false)
    setEnglishTtsTestError(null)
    setEnglishTtsTestText('')
    setEnglishTtsTestDescription('')
  }, [])
  // ── END TEMPORARY English TTS Test handler ─────────────────────────────────

  // -- TEMPORARY Mixed TTS Test handler -------------------------------------
  // REMOVE this handler after mixed TTS testing is complete.
  const handleMixedTtsTestGenerate = useCallback(async () => {
    const text = mixedTtsTestText.trim()
    if (!text || mixedTtsTestLoading) return

    const thisId = ++mixedTtsTestRequestIdRef.current

    setMixedTtsTestAudioUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return null
    })
    setMixedTtsTestLoading(true)
    setMixedTtsTestError(null)
    setMixedTtsTestPlaying(false)
    setMixedTtsTestSegments(null)
    setMixedTtsNormalizedText(null)
    setMixedTtsModeUsed(null)

    try {
      const result = await testSynthesizeMixedSpeech(text, mixedTtsVoiceMatching, mixedTtsTestMode)
      if (thisId !== mixedTtsTestRequestIdRef.current) return
      const url = URL.createObjectURL(result.blob)
      setMixedTtsTestAudioUrl(url)
      setMixedTtsTestSegments(result.segments.length > 0 ? result.segments : null)
      setMixedTtsNormalizedText(result.normalizedText)
      setMixedTtsModeUsed(result.modeUsed)
    } catch (err: unknown) {
      if (thisId !== mixedTtsTestRequestIdRef.current) return
      setMixedTtsTestError(
        err instanceof Error ? err.message : 'Mixed TTS test failed -- check Modal logs.'
      )
    } finally {
      if (thisId === mixedTtsTestRequestIdRef.current) {
        setMixedTtsTestLoading(false)
      }
    }
  }, [mixedTtsTestText, mixedTtsTestLoading, mixedTtsVoiceMatching, mixedTtsTestMode])

  const handleMixedTtsTestReset = useCallback(() => {
    mixedTtsTestRequestIdRef.current++
    setMixedTtsTestAudioUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return null
    })
    setMixedTtsTestLoading(false)
    setMixedTtsTestPlaying(false)
    setMixedTtsTestError(null)
    setMixedTtsTestText('')
    setMixedTtsTestSegments(null)
    setMixedTtsNormalizedText(null)
    setMixedTtsModeUsed(null)
  }, [])
  // -- END TEMPORARY Mixed TTS Test handler ---------------------------------

  // -- TEMPORARY Mode C Multilingual TTS Test handler -----------------------
  // REMOVE this handler after Mode C evaluation is complete.
  const _MODE_C_TEST_SENTENCES = [
    'Artificial Intelligence பயன்படுத்தி difficult topics-ஐ simple ஆக explain பண்ணலாம்.',
    'இன்றைய technology மாணவர்களின் learning experience-ஐ improve பண்ணுகிறது.',
    'Chocolate-ல் உள்ள theobromine நாய்களுக்கு நஞ்சாகும்.',
    'Machine learning மற்றும் data science இன்று பல இடங்களில் பயன்படுத்தப்படுகிறது.',
    'AI tools மூலம் students தங்கள் own pace-ல் learn பண்ணலாம்.',
    'GPT-4, API, CPU மற்றும் GPU பற்றி explain பண்ணவும்.',
    'cloud-based systems மற்றும் online education மிகவும் useful.',
    'நாய்கள் மிகவும் விசுவாசமானவை.',
    'Artificial intelligence helps students learn better.',
  ]

  const handleMultilingualTtsTestGenerate = useCallback(async () => {
    const text = multilingualTtsTestText.trim()
    if (!text || multilingualTtsTestLoading) return

    const thisId = ++multilingualTtsTestRequestIdRef.current

    setMultilingualTtsTestAudioUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return null
    })
    setMultilingualTtsTestLoading(true)
    setMultilingualTtsTestError(null)
    setMultilingualTtsTestPlaying(false)
    setMultilingualTtsLatencyMs(null)

    try {
      const result = await testSynthesizeMultilingualSpeech(text)
      if (thisId !== multilingualTtsTestRequestIdRef.current) return
      const url = URL.createObjectURL(result.blob)
      setMultilingualTtsTestAudioUrl(url)
      setMultilingualTtsLatencyMs(result.latencyMs)
    } catch (err: unknown) {
      if (thisId !== multilingualTtsTestRequestIdRef.current) return
      setMultilingualTtsTestError(
        err instanceof Error ? err.message : 'Mode C TTS failed — check Modal logs.'
      )
    } finally {
      if (thisId === multilingualTtsTestRequestIdRef.current) {
        setMultilingualTtsTestLoading(false)
      }
    }
  }, [multilingualTtsTestText, multilingualTtsTestLoading])

  const handleMultilingualTtsTestReset = useCallback(() => {
    multilingualTtsTestRequestIdRef.current++
    setMultilingualTtsTestAudioUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return null
    })
    setMultilingualTtsTestLoading(false)
    setMultilingualTtsTestPlaying(false)
    setMultilingualTtsTestError(null)
    setMultilingualTtsTestText('')
    setMultilingualTtsLatencyMs(null)
  }, [])
  // -- END TEMPORARY Mode C Multilingual TTS Test handler -------------------

  // -- TEMPORARY Mode D Indic Parler Mixed TTS Test handler -----------------
  // REMOVE this handler after Mode D evaluation is complete.
  const _MODE_D_TEST_SENTENCES = [
    'Artificial Intelligence பயன்படுத்தி difficult topics-ஐ simple ஆக explain பண்ணலாம்.',
    'இன்றைய technology மாணவர்களின் learning experience-ஐ improve பண்ணுகிறது.',
    'Chocolate-ல் உள்ள theobromine நாய்களுக்கு நஞ்சாகும்.',
    'Machine learning மற்றும் data science இன்று பல துறைகளில் பயன்படுத்தப்படுகிறது.',
    'AI tools மூலம் students தங்கள் own pace-ல் learn பண்ணலாம்.',
    'GPT-4, API, CPU மற்றும் GPU பற்றி explain பண்ணவும்.',
    'cloud-based systems மற்றும் online education மிகவும் useful.',
    'இன்றைய digital world-ல் cybersecurity மிகவும் important ஆகிவிட்டது.',
    'தமிழ் ஒரு அழகான மொழி. மாணவர்கள் புதிய விஷயங்களை எளிதாக கற்றுக்கொள்ள முடியும்.',
    'Artificial intelligence can help students understand difficult topics in a simple way.',
  ]

  const handleIndicParlerMixedGenerate = useCallback(async () => {
    const text = indicParlerMixedText.trim()
    if (!text || indicParlerMixedLoading) return

    const thisId = ++indicParlerMixedRequestIdRef.current

    setIndicParlerMixedAudioUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return null
    })
    setIndicParlerMixedLoading(true)
    setIndicParlerMixedError(null)
    setIndicParlerMixedPlaying(false)
    setIndicParlerMixedLatencyMs(null)
    setIndicParlerMixedSampleRate(null)
    setIndicParlerMixedSpeaker(null)

    try {
      const result = await testSynthesizeIndicParlerMixedSpeech(text)
      if (thisId !== indicParlerMixedRequestIdRef.current) return
      const url = URL.createObjectURL(result.blob)
      setIndicParlerMixedAudioUrl(url)
      setIndicParlerMixedLatencyMs(result.latencyMs)
      setIndicParlerMixedSampleRate(result.sampleRate)
      setIndicParlerMixedSpeaker(result.speaker)
    } catch (err: unknown) {
      if (thisId !== indicParlerMixedRequestIdRef.current) return
      setIndicParlerMixedError(
        err instanceof Error ? err.message : 'Mode D TTS failed — check Modal logs.'
      )
    } finally {
      if (thisId === indicParlerMixedRequestIdRef.current) {
        setIndicParlerMixedLoading(false)
      }
    }
  }, [indicParlerMixedText, indicParlerMixedLoading])

  const handleIndicParlerMixedReset = useCallback(() => {
    indicParlerMixedRequestIdRef.current++
    setIndicParlerMixedAudioUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return null
    })
    setIndicParlerMixedLoading(false)
    setIndicParlerMixedPlaying(false)
    setIndicParlerMixedError(null)
    setIndicParlerMixedText('')
    setIndicParlerMixedLatencyMs(null)
    setIndicParlerMixedSampleRate(null)
    setIndicParlerMixedSpeaker(null)
  }, [])
  // -- END TEMPORARY Mode D Indic Parler Mixed TTS Test handler -------------

  // ── TEMPORARY Sinhala VITS TTS Test handler ───────────────────────────────
  // REMOVE this block after Sinhala TTS evaluation is complete.
  const _SINHALA_TEST_SENTENCES = [
    'සිංහල භාෂාව ශ්‍රී ලංකාවේ ප්‍රධාන භාෂාවක් වන අතර එයට දිගු ඉතිහාසයක් ඇත.',
    'අද අධ්‍යාපනයේ සිසුන්ට නව දේවල් ඉගෙන ගැනීමට බොහෝ පහසුකම් තිබෙනවා. ගුරුවරුන් සමහර අවස්ථාවල AI tools භාවිතා කරනවා. හොඳ learning experience එකක් ලබා ගැනීමට නිවැරදි මඟපෙන්වීම ඉතා වැදගත්.',
    'ලෝකයේ විවිධ සුනඛ වර්ග ජනප්‍රියයි. Labrador Retriever පවුල් සමඟ හොඳින් හැසිරෙන සුනඛ වර්ගයකි. German Shepherd ඉතා බුද්ධිමත් සුනඛ වර්ගයකි. Golden Retriever දරුවන් සමඟ හොඳින් හැසිරෙයි.',
    'Artificial Intelligence අද අධ්‍යාපනයේ වැදගත් technology එකක්. Machine learning models භාවිතා කරලා difficult concepts පහසුවෙන් explain කරන්න පුළුවන්.',
  ]

  const handleSinhalaTtsGenerate = useCallback(async () => {
    const text = sinhalaTtsText.trim()
    if (!text || sinhalaTtsLoading) return

    const thisId = ++sinhalaTtsRequestIdRef.current

    setSinhalaTtsAudioUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return null
    })
    setSinhalaTtsLoading(true)
    setSinhalaTtsError(null)
    setSinhalaTtsPlaying(false)
    setSinhalaTtsLatencyMs(null)
    setSinhalaTtsSampleRate(null)
    setSinhalaRomanized(null)
    setSinhalaPhoneticPreview(null)

    // Preview first so unknown spans populate the persistent cache before audio.
    setSinhalaRomanizeLoading(true)
    if (sinhalaMixedPhonetics) {
      try {
        const preview = await testSinhalaPhoneticPreview(text)
        if (thisId === sinhalaTtsRequestIdRef.current) {
          setSinhalaPhoneticPreview(preview)
          setSinhalaRomanized(preview.romanized)
        }
      } catch { /* synthesis still has a safe raw-English fallback */ }
      finally { if (thisId === sinhalaTtsRequestIdRef.current) setSinhalaRomanizeLoading(false) }
    } else {
      testSinhalaRomanize(text)
        .then((r) => { if (thisId === sinhalaTtsRequestIdRef.current) setSinhalaRomanized(r.romanized) })
        .catch(() => {/* silent — romanize preview is best-effort */})
        .finally(() => { if (thisId === sinhalaTtsRequestIdRef.current) setSinhalaRomanizeLoading(false) })
    }

    try {
      const result = await testSynthesizeSinhalaSpeech(text, sinhalaMixedPhonetics)
      if (thisId !== sinhalaTtsRequestIdRef.current) return
      const url = URL.createObjectURL(result.blob)
      setSinhalaTtsAudioUrl(url)
      setSinhalaTtsLatencyMs(result.latencyMs)
      setSinhalaTtsSampleRate(result.sampleRate)
    } catch (err: unknown) {
      if (thisId !== sinhalaTtsRequestIdRef.current) return
      setSinhalaTtsError(
        err instanceof Error ? err.message : 'Sinhala TTS failed — check Modal logs.'
      )
    } finally {
      if (thisId === sinhalaTtsRequestIdRef.current) {
        setSinhalaTtsLoading(false)
      }
    }
  }, [sinhalaTtsText, sinhalaTtsLoading, sinhalaMixedPhonetics])

  const handleSinhalaTtsReset = useCallback(() => {
    sinhalaTtsRequestIdRef.current++
    setSinhalaTtsAudioUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return null
    })
    setSinhalaTtsLoading(false)
    setSinhalaTtsPlaying(false)
    setSinhalaTtsError(null)
    setSinhalaTtsText('')
    setSinhalaTtsLatencyMs(null)
    setSinhalaTtsSampleRate(null)
    setSinhalaRomanized(null)
    setSinhalaRomanizeLoading(false)
    setSinhalaPhoneticPreview(null)
  }, [])
  // ── END TEMPORARY Sinhala VITS TTS Test handler ───────────────────────────

  const displayedResult = qaResult ?? typedResult
  const showingTypedResult = !qaResult && !!typedResult


  // ─────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-page-gradient">

      {/* ── Fixed Header ─────────────────────────────────────── */}
      <header className="glass fixed top-0 left-0 right-0 z-50">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="glow-dot" />
            <span className="font-semibold text-sm text-white tracking-tight">VoiceLearn AI</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[11px] font-semibold rounded-full px-3 py-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              {language === 'tamil' ? 'Tamil ASR · Qwen3' : 'Whisper V3'}
            </span>
            <span className="inline-flex items-center gap-1.5 bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-[11px] font-semibold rounded-full px-3 py-1">
              RAG · Phase 2
            </span>
          </div>
        </div>
      </header>

      {/* ── Page body ─────────────────────────────────────────── */}
      <main className="pt-14 pb-24">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 py-10 flex flex-col gap-5">

          {/* ── Hero ──────────────────────────────────────────── */}
          <div className="text-center flex flex-col items-center gap-3 pt-4 pb-1">
            <h1 className="text-3xl sm:text-4xl font-bold text-gradient-subtle tracking-tight">
              AI Study Assistant
            </h1>
            <p className="text-sm text-white/40 max-w-sm leading-relaxed">
              Upload your lecture docs, ask questions by voice, get answers in your language.
            </p>
          </div>

          {/* ── SECTION 1 — Language Selector ─────────────────── */}
          <section className="glass-card rounded-3xl p-5 sm:p-6">
            <SectionLabel icon="🌐" text="Response Language" />
            <LanguageSelector value={language} onChange={setLanguage} />
          </section>

          {/* ── SECTION 2 — Document Upload ───────────────────── */}
          <section className="glass-card rounded-3xl overflow-hidden">
            <button
              type="button"
              id="doc-panel-toggle"
              onClick={toggleDocPanel}
              className="w-full flex items-center justify-between px-5 sm:px-6 py-4 hover:bg-white/[0.02] transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className="text-lg">📄</span>
                <span className="text-sm font-semibold text-white/80">Documents</span>
                {docs.length > 0 && (
                  <span className="bg-brand-500/15 border border-brand-500/25 text-brand-400 text-[11px] font-bold rounded-full px-2 py-0.5">
                    {docs.length}
                  </span>
                )}
              </div>
              <ChevronIcon open={docPanelOpen} />
            </button>

            {docPanelOpen && (
              <div className="px-5 sm:px-6 pb-5 flex flex-col gap-4 border-t border-white/[0.06]">
                <div
                  onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className={`mt-4 flex flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed py-8 cursor-pointer transition-all duration-200
                    ${dragOver ? 'border-brand-500/70 bg-brand-500/10' : 'border-white/10 hover:border-white/20 hover:bg-white/[0.02]'}
                    ${uploading ? 'pointer-events-none opacity-50' : ''}`}
                >
                  {uploading ? (
                    <>
                      <div className="w-7 h-7 rounded-full border-2 border-white/20 border-t-white/80 animate-spin" />
                      <p className="text-sm text-white/50">Uploading &amp; indexing…</p>
                    </>
                  ) : (
                    <>
                      <span className="text-2xl">⬆️</span>
                      <p className="text-sm font-medium text-white/60">
                        Drop file here or <span className="text-brand-400">click to browse</span>
                      </p>
                      <p className="text-[11px] text-white/30">PDF · PPTX · DOCX · XLSX · TXT · MD</p>
                    </>
                  )}
                  <input
                    ref={fileInputRef}
                    type="file"
                    className="sr-only"
                    accept=".pdf,.pptx,.docx,.xlsx,.txt,.md"
                    onChange={(e) => {
                      const f = e.target.files?.[0]
                      if (f) handleFileUpload(f)
                      e.target.value = ''
                    }}
                  />
                </div>

                {uploadError && (
                  <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-xl px-3 py-2.5">
                    <span className="text-red-400 text-sm shrink-0">⚠</span>
                    <p className="text-xs text-red-400">{uploadError}</p>
                  </div>
                )}

                {docs.length > 0 ? (
                  <ul className="flex flex-col gap-2">
                    {docs.map((doc) => (
                      <DocRow key={doc.document_id} doc={doc} onDelete={handleDelete} />
                    ))}
                  </ul>
                ) : docsLoaded ? (
                  <p className="text-center text-[12px] text-white/25 py-2">
                    No documents yet — upload one above
                  </p>
                ) : null}
              </div>
            )}
          </section>

          {/* ── SECTION 3 — Voice Query ───────────────────────── */}
          <section className="glass-card rounded-3xl p-6 sm:p-8 flex flex-col gap-6">
            <SectionLabel icon="🎤" text="Ask a Question" />

                {/* Recorder disabled while correcting or asking */}
            <VoiceRecorder
              language={language}
              onTranscript={handleTranscript}
              onError={handleVoiceError}
              disabled={phase === 'correcting' || phase === 'asking'}
            />

            {/* TEMPORARY: removable multilingual RAG test entry point. */}
            <div className="border-t border-dashed border-amber-400/25 pt-5 flex flex-col gap-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-amber-300/80">Temporary RAG Test</p>
                  <p className="mt-1 text-xs text-white/35">Type a Tamil, Sinhala, or English question to bypass audio and ASR.</p>
                </div>
                <span className="shrink-0 rounded-full border border-amber-400/20 bg-amber-400/10 px-2 py-1 text-[10px] font-semibold text-amber-200/80">DEV ONLY</span>
              </div>
              <textarea
                id="typed-rag-question"
                value={typedQuestion}
                onChange={(e) => setTypedQuestion(e.target.value)}
                disabled={typedAsking}
                rows={3}
                placeholder="Type Question (e.g. நாயின் வரலாறு பற்றி கூறு)"
                className="w-full bg-white/[0.03] border border-white/[0.10] focus:border-amber-400/50 rounded-2xl px-4 py-3 text-sm text-white/90 leading-relaxed resize-none outline-none transition-all placeholder:text-white/25 disabled:opacity-60"
              />

              <label className="flex items-center gap-2 text-[11px] text-emerald-200/70 cursor-pointer select-none">
                <input
                  id="sinhala-mixed-phonetics-toggle"
                  type="checkbox"
                  checked={sinhalaMixedPhonetics}
                  onChange={(e) => setSinhalaMixedPhonetics(e.target.checked)}
                  disabled={sinhalaTtsLoading}
                  className="accent-emerald-500"
                />
                Mixed Sinhala + English phonetic preprocessing (development only)
              </label>

              <div className="flex items-center justify-between gap-3">
                <span className="text-[11px] text-white/25">Uses the selected response language.</span>
                <button
                  id="typed-rag-ask-btn"
                  type="button"
                  onClick={handleTypedAsk}
                  disabled={typedAsking || !typedQuestion.trim()}
                  className="inline-flex items-center gap-2 bg-amber-400/15 hover:bg-amber-400/20 border border-amber-300/25 text-amber-100 text-sm font-semibold px-5 py-2.5 rounded-xl transition-all disabled:opacity-40 disabled:pointer-events-none"
                >
                  {typedAsking ? 'Searching…' : 'Ask'}
                </button>
              </div>
              {typedAskError && (
                <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-xl px-3 py-2.5">
                  <span className="text-red-400 text-sm shrink-0">⚠</span>
                  <p className="text-xs text-red-400">{typedAskError}</p>
                </div>
              )}
            </div>

            {voiceError && (
              <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-xl px-3 py-2.5">
                <span className="text-red-400 text-sm shrink-0">⚠</span>
                <p className="text-xs text-red-400">{voiceError}</p>
              </div>
            )}

            {/* ────────────────────────────────────────────────────── */}
            {/* STEP 1 — Transcript */}
            {/* ────────────────────────────────────────────────────── */}
            {sttResult && phase !== 'idle' && (
              <div className="flex flex-col gap-4 animate-fade-up">
                <div className="divider" />

                {/* Transcript card */}
                <div className="flex flex-col gap-2">
                  {/* Raw transcript label */}
                  <div className="flex items-center gap-2">
                    <StepBadge n={1} done={phase !== 'transcript'} />
                    <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-white/30">
                      Raw ASR Transcript
                    </span>
                  </div>
                  <div className="bg-white/[0.03] border border-white/[0.08] rounded-2xl px-4 py-3">
                    <p className="text-white/85 text-[15px] leading-relaxed font-medium">
                      &ldquo;{sttResult.transcript || <span className="text-white/30 italic text-sm">No speech detected</span>}&rdquo;
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Chip label="Mode"     value={sttResult.selected_language}              variant="brand" />
                    <Chip label="Detected" value={sttResult.detected_language.toUpperCase()} variant="accent" />
                    <Chip label="Latency"  value={`${sttResult.duration_ms} ms`}             variant="dim" />
                  </div>
                </div>

                {/* Transcript-phase action buttons */}
                {phase === 'transcript' && sttResult.transcript && (
                  <div className="flex flex-wrap items-center gap-3">
                    <button
                      id="correct-transcript-btn"
                      type="button"
                      onClick={handleCorrect}
                      className="inline-flex items-center gap-2 bg-gradient-to-r from-brand-600 to-accent-600 hover:from-brand-500 hover:to-accent-500 text-white text-sm font-semibold px-5 py-2.5 rounded-xl transition-all shadow-brand hover:scale-[1.03] active:scale-[0.97]"
                    >
                      🔧 Fix Transcript
                    </button>
                    <button
                      id="ask-direct-btn"
                      type="button"
                      onClick={handleAskDirect}
                      className="inline-flex items-center gap-2 bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 text-white/60 hover:text-white/80 text-sm font-medium px-4 py-2.5 rounded-xl transition-all"
                    >
                      Ask Directly →
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* ────────────────────────────────────────────────────── */}
            {/* STEP 2 — Correcting spinner */}
            {/* ────────────────────────────────────────────────────── */}
            {phase === 'correcting' && (
              <div className="flex items-center gap-3 animate-fade-up">
                <div className="w-5 h-5 rounded-full border-2 border-brand-500/30 border-t-brand-400 animate-spin shrink-0" />
                <span className="text-sm text-brand-400 animate-pulse">
                  Correcting transcript with Gemma 4 12B…
                </span>
              </div>
            )}

            {/* ────────────────────────────────────────────────────── */}
            {/* STEP 2 — Review corrected transcript */}
            {/* ────────────────────────────────────────────────────── */}
            {(phase === 'corrected' || phase === 'asking' || phase === 'answered') && (
              <div className="flex flex-col gap-4 animate-fade-up">
                <div className="divider" />

                <div className="flex flex-col gap-2">
                  <div className="flex items-center gap-2">
                    <StepBadge n={2} done={phase === 'asking' || phase === 'answered'} />
                    <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-white/30">
                      🔧 Corrected Transcript — Review &amp; Edit
                    </span>
                  </div>

                  {correctError && (
                    <div className="flex items-start gap-2 bg-sky-500/10 border border-sky-500/20 rounded-xl px-3 py-2">
                      <span className="text-sky-400 text-xs shrink-0">ℹ</span>
                      <p className="text-xs text-sky-400">{correctError}</p>
                    </div>
                  )}

                  {/* Editable corrected transcript */}
                  <div className="relative">
                    <textarea
                      id="corrected-transcript-textarea"
                      value={correctedTranscriptText}
                      onChange={(e) => setCorrectedTranscriptText(e.target.value)}
                      disabled={phase === 'asking' || phase === 'answered'}
                      rows={3}
                      className="w-full bg-brand-500/8 border border-brand-500/30 focus:border-brand-500/60 rounded-2xl px-4 py-3 text-sm text-white/90 leading-relaxed resize-none outline-none transition-all placeholder:text-white/20 disabled:opacity-60 disabled:cursor-not-allowed"
                      placeholder="Corrected transcript will appear here…"
                    />
                    {phase === 'corrected' && (
                      <span className="absolute top-2.5 right-3 text-[10px] text-white/20 font-medium select-none">
                        editable
                      </span>
                    )}
                  </div>

                  {/* Ask action */}
                  {phase === 'corrected' && (
                    <div className="flex flex-wrap items-center gap-3 mt-1">
                      <button
                        id="use-and-ask-btn"
                        type="button"
                        onClick={handleAsk}
                        disabled={!correctedTranscriptText.trim()}
                        className="inline-flex items-center gap-2 bg-gradient-to-r from-brand-600 to-accent-600 hover:from-brand-500 hover:to-accent-500 disabled:opacity-40 disabled:pointer-events-none text-white text-sm font-semibold px-5 py-2.5 rounded-xl transition-all shadow-brand hover:scale-[1.03] active:scale-[0.97]"
                      >
                        🔍 Use &amp; Ask
                      </button>
                      <button
                        type="button"
                        onClick={() => setPhase('transcript')}
                        className="text-[12px] font-medium text-white/30 hover:text-white/60 transition-colors"
                      >
                        ← Use original instead
                      </button>
                    </div>
                  )}
                </div>

                {/* Asking spinner */}
                {phase === 'asking' && (
                  <div className="flex items-center gap-3">
                    <div className="w-5 h-5 rounded-full border-2 border-accent-500/30 border-t-accent-400 animate-spin shrink-0" />
                    <span className="text-sm text-accent-400 animate-pulse">
                      Searching documents &amp; generating answer…
                    </span>
                  </div>
                )}

                {/* Ask error */}
                {askError && (
                  <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-xl px-3 py-2.5">
                    <span className="text-red-400 text-sm shrink-0">⚠</span>
                    <p className="text-xs text-red-400">{askError}</p>
                  </div>
                )}
              </div>
            )}

            {/* ────────────────────────────────────────────────────── */}
            {/* STEP 3 — Answer */}
            {/* ────────────────────────────────────────────────────── */}
            {((phase === 'answered' && qaResult) || typedResult) && displayedResult && (
              <div ref={answerRef} className="flex flex-col gap-4 animate-fade-up">
                <div className="divider" />

                <div className="flex flex-col gap-2">
                  <div className="flex items-center gap-2">
                    <StepBadge n={3} done />
                    <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-white/30">
                      {showingTypedResult ? 'Temporary RAG Test Answer' : 'Answer'} · {language}
                    </span>
                  </div>
                  <div className="bg-white/[0.03] border border-white/[0.08] rounded-2xl px-5 py-4">
                    <p className="text-white/90 text-[15px] leading-relaxed whitespace-pre-wrap">
                      {displayedResult.answer}
                    </p>
                  </div>
                </div>

                {/* ── Tamil TTS audio widget (Tamil language only) ──── */}
                {language === 'tamil' && (
                  <div className="flex flex-col gap-2">
                    {/* Hidden <audio> element — controlled imperatively */}
                    {tamilAudioUrl && (
                      <audio
                        ref={tamilAudioRef}
                        src={tamilAudioUrl}
                        onEnded={() => setTamilAudioPlaying(false)}
                        onPause={() => setTamilAudioPlaying(false)}
                        onPlay={() => setTamilAudioPlaying(true)}
                        preload="auto"
                        className="sr-only"
                      />
                    )}

                    {tamilAudioLoading && (
                      <div className="flex items-center gap-2 bg-indigo-500/8 border border-indigo-500/20 rounded-xl px-4 py-2.5">
                        <div className="w-4 h-4 rounded-full border-2 border-indigo-400/30 border-t-indigo-400 animate-spin shrink-0" />
                        <span className="text-xs text-indigo-300/80 animate-pulse">
                          Generating Tamil audio…
                        </span>
                      </div>
                    )}

                    {tamilAudioUrl && !tamilAudioLoading && (
                      <div className="flex items-center gap-3 bg-indigo-500/8 border border-indigo-500/20 rounded-xl px-4 py-2.5">
                        <button
                          id="tamil-tts-play-btn"
                          type="button"
                          onClick={() => {
                            const audio = tamilAudioRef.current
                            if (!audio) return
                            if (tamilAudioPlaying) {
                              audio.pause()
                            } else {
                              audio.play()
                            }
                          }}
                          className="flex items-center gap-2 bg-indigo-500/20 hover:bg-indigo-500/30 border border-indigo-400/30 text-indigo-200 text-xs font-semibold px-3 py-1.5 rounded-lg transition-all hover:scale-[1.03] active:scale-[0.97]"
                        >
                          {tamilAudioPlaying ? (
                            <>
                              <PauseIcon />
                              Pause
                            </>
                          ) : (
                            <>
                              <PlayIcon />
                              Play Audio
                            </>
                          )}
                        </button>
                        <span className="text-[11px] text-indigo-300/50">Tamil · Jaya · Indic Parler-TTS</span>
                      </div>
                    )}

                    {tamilAudioError && !tamilAudioLoading && (
                      <div className="flex items-center gap-2 bg-white/[0.03] border border-white/[0.08] rounded-xl px-4 py-2">
                        <span className="text-white/30 text-xs">🔇</span>
                        <span className="text-[11px] text-white/30">
                          Audio unavailable — text answer is complete.
                        </span>
                      </div>
                    )}
                  </div>
                  )}

                {/* ── English TTS audio widget (English language only) ── */}
                {language === 'english' && (
                  <div className="flex flex-col gap-2">
                    {/* Hidden <audio> element — controlled imperatively */}
                    {englishAudioUrl && (
                      <audio
                        ref={englishAudioRef}
                        src={englishAudioUrl}
                        onEnded={() => setEnglishAudioPlaying(false)}
                        onPause={() => setEnglishAudioPlaying(false)}
                        onPlay={() => setEnglishAudioPlaying(true)}
                        preload="auto"
                        className="sr-only"
                      />
                    )}

                    {englishAudioLoading && (
                      <div className="flex items-center gap-2 bg-teal-500/8 border border-teal-500/20 rounded-xl px-4 py-2.5">
                        <div className="w-4 h-4 rounded-full border-2 border-teal-400/30 border-t-teal-400 animate-spin shrink-0" />
                        <span className="text-xs text-teal-300/80 animate-pulse">
                          Generating English audio…
                        </span>
                      </div>
                    )}

                    {englishAudioUrl && !englishAudioLoading && (
                      <div className="flex items-center gap-3 bg-teal-500/8 border border-teal-500/20 rounded-xl px-4 py-2.5">
                        <button
                          id="english-tts-play-btn"
                          type="button"
                          onClick={() => {
                            const audio = englishAudioRef.current
                            if (!audio) return
                            if (englishAudioPlaying) {
                              audio.pause()
                            } else {
                              audio.play()
                            }
                          }}
                          className="flex items-center gap-2 bg-teal-500/20 hover:bg-teal-500/30 border border-teal-400/30 text-teal-200 text-xs font-semibold px-3 py-1.5 rounded-lg transition-all hover:scale-[1.03] active:scale-[0.97]"
                        >
                          {englishAudioPlaying ? (
                            <><PauseIcon />Pause</>
                          ) : (
                            <><PlayIcon />Play Audio</>
                          )}
                        </button>
                        <span className="text-[11px] text-teal-300/50">English · Parler-TTS Mini v1</span>
                      </div>
                    )}

                    {englishAudioError && !englishAudioLoading && (
                      <div className="flex items-center gap-2 bg-white/[0.03] border border-white/[0.08] rounded-xl px-4 py-2">
                        <span className="text-white/30 text-xs">🔇</span>
                        <span className="text-[11px] text-white/30">
                          Audio unavailable — text answer is complete.
                        </span>
                      </div>
                    )}
                  </div>
                )}

                {/* References */}
                {displayedResult.references.length > 0 && (
                  <div className="flex flex-col gap-2">
                    <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-white/30">
                      Sources
                    </span>
                    <div className="flex flex-col gap-2">
                      {displayedResult.references.map((ref, i) => (
                        <div key={i} className="flex items-start gap-3 bg-white/[0.02] border border-white/[0.07] rounded-xl px-4 py-3">
                          <span className="text-[11px] text-white/25 font-mono mt-0.5 shrink-0">#{i + 1}</span>
                          <div className="flex flex-col gap-1 min-w-0 flex-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-[12px] font-semibold text-white/70 truncate">{ref.filename}</span>
                              {ref.page && (
                                <span className="text-[10px] text-white/30 bg-white/5 rounded px-1.5 py-0.5">p.{ref.page}</span>
                              )}
                              <span className="text-[10px] text-accent-400/70 ml-auto">
                                {(ref.score * 100).toFixed(0)}% match
                              </span>
                            </div>
                            <p className="text-[12px] text-white/40 leading-relaxed line-clamp-2">{ref.excerpt}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Ask again */}
                <button
                  type="button"
                  id="ask-again-btn"
                  onClick={showingTypedResult ? () => {
                    setTypedResult(null)
                    setTypedAskError(null)
                  } : handleReset}
                  className="self-start text-[12px] font-medium text-white/35 hover:text-white/60 transition-colors mt-1"
                >
                  ← Ask another question
                </button>
              </div>
            )}
          </section>

          {/* ── TEMPORARY SECTION START ──────────────────────────────────── */}
          {/* Tamil TTS Isolated Test Area                                    */}
          {/* REMOVE: this entire section block after TTS testing is complete  */}
          {/* Independent of ALL ASR / RAG state — has its own state only.    */}
          {_USE_TAMIL_TTS_TEST && (
            <section className="glass-card rounded-3xl p-5 sm:p-6 flex flex-col gap-4 border border-dashed border-violet-400/30">

              {/* Section header */}
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-violet-300/80 flex items-center gap-2">
                    <span>🔊</span>
                    Temporary Tamil TTS Test
                  </p>
                  <p className="mt-1 text-xs text-white/35">
                    Type Tamil text → hear how Indic Parler-TTS pronounces it.
                    Completely isolated from ASR / RAG.
                  </p>
                </div>
                <span className="shrink-0 rounded-full border border-violet-400/25 bg-violet-400/10 px-2 py-1 text-[10px] font-semibold text-violet-200/80">
                  DEV ONLY
                </span>
              </div>

              {/* Textarea — labelled "Temporary Tamil TTS Test" for accessibility */}
              <textarea
                id="tts-test-textarea"
                aria-label="Temporary Tamil TTS Test"
                value={ttsTestText}
                onChange={(e) => setTtsTestText(e.target.value)}
                disabled={ttsTestLoading}
                rows={4}
                placeholder={
                  'Test 1: நாயின் வரலாறு மிகவும் பழமையானது.\n' +
                  'Test 2: பிரபலமான நாய் இனங்களில் லாப்ரடோர் ரெட்ரீவர், ஜெர்மன் ஷெப்பர்ட் மற்றும் கோல்டன் ரெட்ரீவர் ஆகியவை அடங்கும்.\n' +
                  'Test 3: வணக்கம். இன்று நாம் நாய்களின் வரலாறு மற்றும் அவற்றின் சிறப்புகளைப் பற்றி அறிந்துகொள்வோம்.'
                }
                className="w-full bg-white/[0.03] border border-violet-400/20 focus:border-violet-400/50 rounded-2xl px-4 py-3 text-sm text-white/90 leading-relaxed resize-none outline-none transition-all placeholder:text-white/20 disabled:opacity-60"
              />

              <label className="flex items-center gap-3 text-xs text-white/55">
                <span className="shrink-0">Test model</span>
                <select
                  value={ttsTestEngine}
                  onChange={(e) => setTtsTestEngine(e.target.value as 'indic-parler' | 'mms')}
                  disabled={ttsTestLoading}
                  className="bg-white/[0.06] border border-violet-400/25 rounded-lg px-3 py-2 text-white/90 outline-none disabled:opacity-60"
                >
                  <option value="indic-parler">AI4Bharat Indic Parler-TTS (Jaya)</option>
                  <option value="mms">Facebook MMS-TTS (Tamil)</option>
                </select>
              </label>

              {/* Action row: Generate Audio + Reset */}
              <div className="flex items-center justify-between gap-3">
                <span className="text-[11px] text-white/25">
                  Only manually typed text is synthesized — never RAG answers.
                </span>
                <div className="flex items-center gap-2">
                  {(ttsTestAudioUrl || ttsTestError) && (
                    <button
                      id="tts-test-reset-btn"
                      type="button"
                      onClick={handleTtsTestReset}
                      className="text-[12px] font-medium text-white/30 hover:text-white/60 transition-colors"
                    >
                      ↺ Reset
                    </button>
                  )}
                  <button
                    id="tts-test-generate-btn"
                    type="button"
                    onClick={handleTtsTestGenerate}
                    disabled={ttsTestLoading || !ttsTestText.trim()}
                    className="inline-flex items-center gap-2 bg-violet-500/20 hover:bg-violet-500/30 border border-violet-400/30 text-violet-100 text-sm font-semibold px-5 py-2.5 rounded-xl transition-all disabled:opacity-40 disabled:pointer-events-none hover:scale-[1.02] active:scale-[0.98]"
                  >
                    {ttsTestLoading ? (
                      <>
                        <div className="w-3.5 h-3.5 rounded-full border-2 border-violet-300/30 border-t-violet-300 animate-spin shrink-0" />
                        Generating…
                      </>
                    ) : (
                      <>🎵 Generate Audio</>
                    )}
                  </button>
                </div>
              </div>

              {/* Loading message */}
              {ttsTestLoading && (
                <div className="flex items-center gap-2 bg-violet-500/8 border border-violet-500/20 rounded-xl px-4 py-2.5">
                  <div className="w-4 h-4 rounded-full border-2 border-violet-400/30 border-t-violet-400 animate-spin shrink-0" />
                  <span className="text-xs text-violet-300/80 animate-pulse">
                    Generating Tamil audio… (first request may take ~90 s for A10G cold-start)
                  </span>
                </div>
              )}

              {/* Hidden <audio> element — controlled imperatively */}
              {ttsTestAudioUrl && (
                <audio
                  ref={ttsTestAudioRef}
                  src={ttsTestAudioUrl}
                  onEnded={() => setTtsTestPlaying(false)}
                  onPause={() => setTtsTestPlaying(false)}
                  onPlay={() => setTtsTestPlaying(true)}
                  preload="auto"
                  className="sr-only"
                />
              )}

              {/* Play / Pause controls */}
              {ttsTestAudioUrl && !ttsTestLoading && (
                <div className="flex items-center gap-3 bg-violet-500/8 border border-violet-500/20 rounded-xl px-4 py-2.5">
                  <button
                    id="tts-test-play-btn"
                    type="button"
                    onClick={() => {
                      const audio = ttsTestAudioRef.current
                      if (!audio) return
                      if (ttsTestPlaying) {
                        audio.pause()
                      } else {
                        audio.play()
                      }
                    }}
                    className="flex items-center gap-2 bg-violet-500/20 hover:bg-violet-500/30 border border-violet-400/30 text-violet-200 text-xs font-semibold px-3 py-1.5 rounded-lg transition-all hover:scale-[1.03] active:scale-[0.97]"
                  >
                    {ttsTestPlaying ? (
                      <><PauseIcon />Pause</>
                    ) : (
                      <><PlayIcon />Play Audio</>
                    )}
                  </button>
                  <span className="text-[11px] text-violet-300/50">
                    Tamil · Jaya · Indic Parler-TTS · AI4Bharat
                  </span>
                </div>
              )}

              {/* Error message */}
              {ttsTestError && !ttsTestLoading && (
                <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-xl px-3 py-2.5">
                  <span className="text-red-400 text-sm shrink-0">⚠</span>
                  <p className="text-xs text-red-400">{ttsTestError}</p>
                </div>
              )}
            </section>
          )}
          {/* ── TEMPORARY SECTION END ────────────────────────────────────── */}

          {/* ── TEMPORARY SECTION START ─────────────────────────────────────── */}
          {/* English TTS Isolated Test Area                                     */}
          {/* REMOVE: this entire section block after English TTS testing        */}
          {/* Independent of ALL ASR / RAG / Tamil state — has its own state.   */}
          {_USE_ENGLISH_TTS_TEST && (
            <section className="glass-card rounded-3xl p-5 sm:p-6 flex flex-col gap-4 border border-dashed border-teal-400/30">

              {/* Section header */}
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-teal-300/80 flex items-center gap-2">
                    <span>🔊</span>
                    Temporary English TTS Test
                  </p>
                  <p className="mt-1 text-xs text-white/35">
                    Type English text → hear how Parler-TTS Mini v1 pronounces it.
                    Completely isolated from ASR / RAG / Tamil TTS.
                  </p>
                </div>
                <span className="shrink-0 rounded-full border border-teal-400/25 bg-teal-400/10 px-2 py-1 text-[10px] font-semibold text-teal-200/80">
                  DEV ONLY
                </span>
              </div>

              {/* English text textarea */}
              <textarea
                id="english-tts-test-textarea"
                aria-label="Temporary English TTS Test"
                value={englishTtsTestText}
                onChange={(e) => setEnglishTtsTestText(e.target.value)}
                disabled={englishTtsTestLoading}
                rows={4}
                placeholder={
                  'Test 1: Artificial intelligence is changing the way students learn and interact with information.\n' +
                  'Test 2: Machine learning algorithms can identify patterns in large datasets that would be impossible for humans to detect manually.\n' +
                  'Test 3: Neural networks are computational models inspired by the structure and function of biological neural networks.'
                }
                className="w-full bg-white/[0.03] border border-teal-400/20 focus:border-teal-400/50 rounded-2xl px-4 py-3 text-sm text-white/90 leading-relaxed resize-none outline-none transition-all placeholder:text-white/20 disabled:opacity-60"
              />

              {/* Voice/style description textarea */}
              <div className="flex flex-col gap-1.5">
                <label className="text-[11px] font-semibold text-teal-300/70 uppercase tracking-[0.08em]">
                  Voice / Style Description <span className="font-normal text-white/30 normal-case">(optional — controls Parler-TTS speaking style)</span>
                </label>
                <textarea
                  id="english-tts-test-description"
                  aria-label="Voice style description"
                  value={englishTtsTestDescription}
                  onChange={(e) => setEnglishTtsTestDescription(e.target.value)}
                  disabled={englishTtsTestLoading}
                  rows={2}
                  placeholder="e.g. A clear, warm English speaker with a calm educational tone, moderate speaking speed, natural pauses, confident delivery, and clean studio-quality audio."
                  className="w-full bg-white/[0.03] border border-teal-400/15 focus:border-teal-400/40 rounded-xl px-4 py-3 text-sm text-white/90 leading-relaxed resize-none outline-none transition-all placeholder:text-white/20 disabled:opacity-60"
                />
              </div>

              {/* Action row: Generate Audio + Reset */}
              <div className="flex items-center justify-between gap-3">
                <span className="text-[11px] text-white/25">
                  Only manually typed text is synthesized — never RAG answers.
                </span>
                <div className="flex items-center gap-2">
                  {(englishTtsTestAudioUrl || englishTtsTestError) && (
                    <button
                      id="english-tts-test-reset-btn"
                      type="button"
                      onClick={handleEnglishTtsTestReset}
                      className="text-[12px] font-medium text-white/30 hover:text-white/60 transition-colors"
                    >
                      ↺ Reset
                    </button>
                  )}
                  <button
                    id="english-tts-test-generate-btn"
                    type="button"
                    onClick={handleEnglishTtsTestGenerate}
                    disabled={englishTtsTestLoading || !englishTtsTestText.trim()}
                    className="inline-flex items-center gap-2 bg-teal-500/20 hover:bg-teal-500/30 border border-teal-400/30 text-teal-100 text-sm font-semibold px-5 py-2.5 rounded-xl transition-all disabled:opacity-40 disabled:pointer-events-none hover:scale-[1.02] active:scale-[0.98]"
                  >
                    {englishTtsTestLoading ? (
                      <>
                        <div className="w-3.5 h-3.5 rounded-full border-2 border-teal-300/30 border-t-teal-300 animate-spin shrink-0" />
                        Generating…
                      </>
                    ) : (
                      <>🎵 Generate Audio</>
                    )}
                  </button>
                </div>
              </div>

              {/* Loading message */}
              {englishTtsTestLoading && (
                <div className="flex items-center gap-2 bg-teal-500/8 border border-teal-500/20 rounded-xl px-4 py-2.5">
                  <div className="w-4 h-4 rounded-full border-2 border-teal-400/30 border-t-teal-400 animate-spin shrink-0" />
                  <span className="text-xs text-teal-300/80 animate-pulse">
                    Generating English audio… (first request may take ~60–90 s for T4 cold-start)
                  </span>
                </div>
              )}

              {/* Hidden <audio> element — controlled imperatively */}
              {englishTtsTestAudioUrl && (
                <audio
                  ref={englishTtsTestAudioRef}
                  src={englishTtsTestAudioUrl}
                  onEnded={() => setEnglishTtsTestPlaying(false)}
                  onPause={() => setEnglishTtsTestPlaying(false)}
                  onPlay={() => setEnglishTtsTestPlaying(true)}
                  preload="auto"
                  className="sr-only"
                />
              )}

              {/* Play / Pause controls */}
              {englishTtsTestAudioUrl && !englishTtsTestLoading && (
                <div className="flex items-center gap-3 bg-teal-500/8 border border-teal-500/20 rounded-xl px-4 py-2.5">
                  <button
                    id="english-tts-test-play-btn"
                    type="button"
                    onClick={() => {
                      const audio = englishTtsTestAudioRef.current
                      if (!audio) return
                      if (englishTtsTestPlaying) {
                        audio.pause()
                      } else {
                        audio.play()
                      }
                    }}
                    className="flex items-center gap-2 bg-teal-500/20 hover:bg-teal-500/30 border border-teal-400/30 text-teal-200 text-xs font-semibold px-3 py-1.5 rounded-lg transition-all hover:scale-[1.03] active:scale-[0.97]"
                  >
                    {englishTtsTestPlaying ? (
                      <><PauseIcon />Pause</>
                    ) : (
                      <><PlayIcon />Play Audio</>
                    )}
                  </button>
                  <span className="text-[11px] text-teal-300/50">
                    English · Parler-TTS Mini v1
                  </span>
                </div>
              )}

              {/* Error message */}
              {englishTtsTestError && !englishTtsTestLoading && (
                <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-xl px-3 py-2.5">
                  <span className="text-red-400 text-sm shrink-0">⚠</span>
                  <p className="text-xs text-red-400">{englishTtsTestError}</p>
                </div>
              )}
            </section>
          )}
          {/* ── TEMPORARY ENGLISH TTS TEST SECTION END ───────────────────────── */}

          {/* -- TEMPORARY SECTION START ------------------------------------- */}
          {/* Mixed Tamil + English TTS Isolated Test Area                     */}
          {/* REMOVE: this entire section after mixed TTS testing is complete  */}
          {_USE_MIXED_TTS_TEST && (
            <section className="glass-card rounded-3xl p-5 sm:p-6 flex flex-col gap-4 border border-dashed border-orange-400/30">

              {/* Section header */}
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-orange-300/80 flex items-center gap-2">
                    <span>&#127925;</span>
                    Temporary Mixed Tamil + English TTS Test
                  </p>
                  <p className="mt-1 text-xs text-white/35">
                    Type code-switched text &#8594; hear IndicF5 (Tamil) + Parler-TTS (English) combined.
                    Completely isolated from ASR / RAG / Tamil / English TTS.
                  </p>
                </div>
                <span className="shrink-0 rounded-full border border-orange-400/25 bg-orange-400/10 px-2 py-1 text-[10px] font-semibold text-orange-200/80">
                  DEV ONLY
                </span>
              </div>

              {/* Mixed text textarea */}
              <textarea
                id="mixed-tts-test-textarea"
                aria-label="Temporary Mixed Tamil + English TTS Test"
                value={mixedTtsTestText}
                onChange={(e) => setMixedTtsTestText(e.target.value)}
                disabled={mixedTtsTestLoading}
                rows={5}
                placeholder={
                  'Paste Tamil+English mixed text here, for example:\n' +
                  'Chocolate- theobromine .\n' +
                  'technology learning experience- improve .'
                }
                className="w-full bg-white/[0.03] border border-orange-400/20 focus:border-orange-400/50 rounded-2xl px-4 py-3 text-sm text-white/90 leading-relaxed resize-none outline-none transition-all placeholder:text-white/20 disabled:opacity-60"
              />

              <fieldset className="flex flex-col gap-2">
                <legend className="text-xs font-semibold text-orange-200/80">Mixed TTS Mode</legend>
                <label className="flex items-start gap-2 text-xs text-white/55">
                  <input type="radio" name="mixed-tts-mode" checked={mixedTtsTestMode === 'a'}
                    onChange={() => setMixedTtsTestMode('a')} disabled={mixedTtsTestLoading}
                    className="accent-orange-400 mt-0.5" />
                  <span><strong className="text-white/75">A — Split Dual-Model</strong><br />Tamil → IndicF5 · English → Parler · joined WAV</span>
                </label>
                <label className="flex items-start gap-2 text-xs text-white/55">
                  <input type="radio" name="mixed-tts-mode" checked={mixedTtsTestMode === 'b'}
                    onChange={() => setMixedTtsTestMode('b')} disabled={mixedTtsTestLoading}
                    className="accent-orange-400 mt-0.5" />
                  <span><strong className="text-white/75">B — Phonetic Single Voice</strong><br />English words → Tamil phonetics · whole text → one IndicF5 voice</span>
                </label>
              </fieldset>

              <label className="flex items-center gap-2 text-xs text-white/55">
                <input
                  type="checkbox"
                  checked={mixedTtsVoiceMatching}
                  onChange={(e) => setMixedTtsVoiceMatching(e.target.checked)}
                  disabled={mixedTtsTestLoading || mixedTtsTestMode === 'b'}
                  className="accent-orange-400"
                />
                Voice matching (Mode A development comparison)
              </label>

              {/* Action row */}
              <div className="flex items-center justify-between gap-3">
                <span className="text-[11px] text-white/25">
                  Only manually typed text is synthesized &#8212; never RAG answers.
                </span>
                <div className="flex items-center gap-2">
                  {(mixedTtsTestAudioUrl || mixedTtsTestError) && (
                    <button
                      id="mixed-tts-test-reset-btn"
                      type="button"
                      onClick={handleMixedTtsTestReset}
                      className="text-[12px] font-medium text-white/30 hover:text-white/60 transition-colors"
                    >
                      &#8634; Reset
                    </button>
                  )}
                  <button
                    id="mixed-tts-test-generate-btn"
                    type="button"
                    onClick={handleMixedTtsTestGenerate}
                    disabled={mixedTtsTestLoading || !mixedTtsTestText.trim()}
                    className="inline-flex items-center gap-2 bg-orange-500/20 hover:bg-orange-500/30 border border-orange-400/30 text-orange-100 text-sm font-semibold px-5 py-2.5 rounded-xl transition-all disabled:opacity-40 disabled:pointer-events-none hover:scale-[1.02] active:scale-[0.98]"
                  >
                    {mixedTtsTestLoading ? (
                      <>
                        <div className="w-3.5 h-3.5 rounded-full border-2 border-orange-300/30 border-t-orange-300 animate-spin shrink-0" />
                        Generating&#8230;
                      </>
                    ) : (
                      <>&#127925; Generate Audio</>
                    )}
                  </button>
                </div>
              </div>

              {/* Loading message */}
              {mixedTtsTestLoading && (
                <div className="flex items-center gap-2 bg-orange-500/8 border border-orange-500/20 rounded-xl px-4 py-2.5">
                  <div className="w-4 h-4 rounded-full border-2 border-orange-400/30 border-t-orange-400 animate-spin shrink-0" />
                  <span className="text-xs text-orange-300/80 animate-pulse">
                    Segmenting text and generating audio&#8230; (first request may take ~120 s for cold-starts)
                  </span>
                </div>
              )}

              {/* Segment preview — from X-Segments response header */}
              {mixedTtsTestSegments && mixedTtsTestSegments.length > 0 && !mixedTtsTestLoading && (
                <div className="flex flex-col gap-1.5">
                  <span className="text-[10px] font-bold uppercase tracking-[0.10em] text-orange-300/60">
                    Detected Segments
                  </span>
                  <div className="flex flex-col gap-1">
                    {mixedTtsTestSegments.map((seg, i) => (
                      <div key={i} className="flex items-start gap-2 bg-white/[0.025] border border-white/[0.07] rounded-lg px-3 py-1.5">
                        <span
                          className={`shrink-0 text-[10px] font-bold rounded px-1.5 py-0.5 mt-0.5 ${
                            seg.lang === 'TA'
                              ? 'bg-indigo-500/20 text-indigo-300'
                              : 'bg-teal-500/20 text-teal-300'
                          }`}
                        >
                          {seg.lang}
                        </span>
                        <span className="text-[12px] text-white/60 leading-relaxed">{seg.text}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {mixedTtsTestMode === 'b' && mixedTtsNormalizedText && !mixedTtsTestLoading && (
                <div className="flex flex-col gap-1.5">
                  <span className="text-[10px] font-bold uppercase tracking-[0.10em] text-orange-300/60">
                    Normalized for IndicF5 (development preview)
                  </span>
                  <div className="bg-white/[0.025] border border-white/[0.07] rounded-lg px-3 py-2 text-[12px] text-white/65 leading-relaxed whitespace-pre-wrap">
                    {mixedTtsNormalizedText}
                  </div>
                  {mixedTtsModeUsed === 'a-fallback' && (
                    <span className="text-[11px] text-amber-300/80">Mode B failed safely; this audio used Mode A fallback.</span>
                  )}
                </div>
              )}

              {/* Hidden audio element */}
              {mixedTtsTestAudioUrl && (
                <audio
                  ref={mixedTtsTestAudioRef}
                  src={mixedTtsTestAudioUrl}
                  onEnded={() => setMixedTtsTestPlaying(false)}
                  onPause={() => setMixedTtsTestPlaying(false)}
                  onPlay={() => setMixedTtsTestPlaying(true)}
                  preload="auto"
                  className="sr-only"
                />
              )}

              {/* Play / Pause controls */}
              {mixedTtsTestAudioUrl && !mixedTtsTestLoading && (
                <div className="flex items-center gap-3 bg-orange-500/8 border border-orange-500/20 rounded-xl px-4 py-2.5">
                  <button
                    id="mixed-tts-test-play-btn"
                    type="button"
                    onClick={() => {
                      const audio = mixedTtsTestAudioRef.current
                      if (!audio) return
                      if (mixedTtsTestPlaying) {
                        audio.pause()
                      } else {
                        audio.play()
                      }
                    }}
                    className="flex items-center gap-2 bg-orange-500/20 hover:bg-orange-500/30 border border-orange-400/30 text-orange-200 text-xs font-semibold px-3 py-1.5 rounded-lg transition-all hover:scale-[1.03] active:scale-[0.97]"
                  >
                    {mixedTtsTestPlaying ? (
                      <><PauseIcon />Pause</>
                    ) : (
                      <><PlayIcon />Play Audio</>
                    )}
                  </button>
                  <span className="text-[11px] text-orange-300/50">
                    {mixedTtsModeUsed === 'b'
                      ? 'Mode B · IndicF5 single Tamil voice'
                      : mixedTtsModeUsed === 'a-fallback'
                        ? 'Mode B request · Mode A fallback'
                        : 'Mode A · IndicF5 (Tamil) + Parler-TTS (English)'}
                  </span>
                </div>
              )}

              {/* Error message */}
              {mixedTtsTestError && !mixedTtsTestLoading && (
                <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-xl px-3 py-2.5">
                  <span className="text-red-400 text-sm shrink-0">&#9888;</span>
                  <p className="text-xs text-red-400">{mixedTtsTestError}</p>
                </div>
              )}
            </section>
          )}
          {/* -- TEMPORARY MIXED TTS TEST SECTION END ------------------------ */}

          {/* -- TEMPORARY MODE C SECTION START ------------------------------ */}
          {/* Mode C: Multilingual Single-Model TTS Isolated Test             */}
          {/* REMOVE: this entire section after Mode C evaluation is complete */}
          {_USE_MULTILINGUAL_TTS_TEST && (
            <section className="glass-card rounded-3xl p-5 sm:p-6 flex flex-col gap-4 border border-dashed border-violet-400/30">

              {/* Section header */}
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-violet-300/80 flex items-center gap-2">
                    <span>&#127908;</span>
                    Mode C — Multilingual Single-Model TTS (Experiment)
                  </p>
                  <p className="mt-1 text-xs text-white/35">
                    Original Tamil&#43;English mixed text &#8594; ONE IndicF5 call &#8594; ONE speaker &#8594; ONE WAV.
                    No transliteration. No segmentation. No split.
                  </p>
                  <p className="mt-1 text-[10px] text-violet-300/40">
                    Model: ai4bharat/IndicF5 &nbsp;·&nbsp; Reference: TAM_F_HAPPY_00001.wav &nbsp;·&nbsp; GPU: A10G
                  </p>
                </div>
                <span className="shrink-0 rounded-full border border-violet-400/25 bg-violet-400/10 px-2 py-1 text-[10px] font-semibold text-violet-200/80">
                  DEV ONLY
                </span>
              </div>

              {/* Quick-fill test sentences */}
              <div className="flex flex-col gap-1.5">
                <span className="text-[10px] font-bold uppercase tracking-[0.10em] text-violet-300/50">
                  Quick-fill test sentences
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {_MODE_C_TEST_SENTENCES.map((s, i) => (
                    <button
                      key={i}
                      type="button"
                      id={`mode-c-sentence-${i + 1}`}
                      disabled={multilingualTtsTestLoading}
                      onClick={() => setMultilingualTtsTestText(s)}
                      className="text-[10px] bg-violet-500/10 hover:bg-violet-500/20 border border-violet-400/20 hover:border-violet-400/40 text-violet-200/70 px-2 py-1 rounded-lg transition-all disabled:opacity-40"
                    >
                      {i < 7 ? `Mixed ${i + 1}` : i === 7 ? 'Pure Tamil' : 'Pure English'}
                    </button>
                  ))}
                </div>
              </div>

              {/* Textarea */}
              <textarea
                id="multilingual-tts-test-textarea"
                aria-label="Mode C Multilingual TTS Test"
                value={multilingualTtsTestText}
                onChange={(e) => setMultilingualTtsTestText(e.target.value)}
                disabled={multilingualTtsTestLoading}
                rows={4}
                placeholder={
                  'Paste Tamil+English mixed text here, for example:\n' +
                  'Artificial Intelligence  difficult topics-  simple  explain .'
                }
                className="w-full bg-white/[0.03] border border-violet-400/20 focus:border-violet-400/50 rounded-2xl px-4 py-3 text-sm text-white/90 leading-relaxed resize-none outline-none transition-all placeholder:text-white/20 disabled:opacity-60"
              />

              {/* Action row */}
              <div className="flex items-center gap-3 flex-wrap">
                <button
                  id="multilingual-tts-test-generate-btn"
                  type="button"
                  onClick={handleMultilingualTtsTestGenerate}
                  disabled={multilingualTtsTestLoading || !multilingualTtsTestText.trim()}
                  className="flex items-center gap-2 bg-violet-600/80 hover:bg-violet-600 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs font-semibold px-4 py-2 rounded-xl transition-all hover:scale-[1.03] active:scale-[0.97]"
                >
                  {multilingualTtsTestLoading ? (
                    <>
                      <div className="w-3.5 h-3.5 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                      Generating&#8230;
                    </>
                  ) : (
                    <>&#127908; Generate (Mode C)</>
                  )}
                </button>

                {(multilingualTtsTestAudioUrl || multilingualTtsTestError) && !multilingualTtsTestLoading && (
                  <button
                    id="multilingual-tts-test-reset-btn"
                    type="button"
                    onClick={handleMultilingualTtsTestReset}
                    className="text-xs text-white/35 hover:text-white/60 transition-colors"
                  >
                    Clear
                  </button>
                )}

                {multilingualTtsLatencyMs !== null && !multilingualTtsTestLoading && (
                  <span className="text-[11px] text-violet-300/60 font-mono">
                    {multilingualTtsLatencyMs >= 1000
                      ? `${(multilingualTtsLatencyMs / 1000).toFixed(1)}s`
                      : `${multilingualTtsLatencyMs}ms`
                    } latency
                  </span>
                )}
              </div>

              {/* Loading status */}
              {multilingualTtsTestLoading && (
                <div className="flex items-center gap-2.5 text-xs text-violet-300/70">
                  <div className="w-3.5 h-3.5 rounded-full border-2 border-violet-400/30 border-t-violet-400 animate-spin shrink-0" />
                  <span>
                    Sending raw mixed text to IndicF5&#8230; (first request may take ~120 s for cold-start)
                  </span>
                </div>
              )}

              {/* Hidden audio element */}
              {multilingualTtsTestAudioUrl && (
                <audio
                  ref={multilingualTtsTestAudioRef}
                  src={multilingualTtsTestAudioUrl}
                  onEnded={() => setMultilingualTtsTestPlaying(false)}
                  onPause={() => setMultilingualTtsTestPlaying(false)}
                  onPlay={() => setMultilingualTtsTestPlaying(true)}
                  preload="auto"
                  className="sr-only"
                />
              )}

              {/* Play / Pause controls */}
              {multilingualTtsTestAudioUrl && !multilingualTtsTestLoading && (
                <div className="flex items-center gap-3 bg-violet-500/8 border border-violet-500/20 rounded-xl px-4 py-2.5">
                  <button
                    id="multilingual-tts-test-play-btn"
                    type="button"
                    onClick={() => {
                      const audio = multilingualTtsTestAudioRef.current
                      if (!audio) return
                      if (multilingualTtsTestPlaying) {
                        audio.pause()
                      } else {
                        audio.play()
                      }
                    }}
                    className="flex items-center gap-2 bg-violet-500/20 hover:bg-violet-500/30 border border-violet-400/30 text-violet-200 text-xs font-semibold px-3 py-1.5 rounded-lg transition-all hover:scale-[1.03] active:scale-[0.97]"
                  >
                    {multilingualTtsTestPlaying ? (
                      <><PauseIcon />Pause</>
                    ) : (
                      <><PlayIcon />Play Audio</>
                    )}
                  </button>
                  <span className="text-[11px] text-violet-300/50">
                    Mode C · IndicF5 direct · one speaker · raw mixed text
                  </span>
                </div>
              )}

              {/* Error message */}
              {multilingualTtsTestError && !multilingualTtsTestLoading && (
                <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-xl px-3 py-2.5">
                  <span className="text-red-400 text-sm shrink-0">&#9888;</span>
                  <p className="text-xs text-red-400">{multilingualTtsTestError}</p>
                </div>
              )}

              {/* Info box — Mode C limitations */}
              <div className="bg-violet-500/5 border border-violet-500/15 rounded-xl px-3 py-2.5 text-[11px] text-violet-300/50 leading-relaxed">
                <strong className="text-violet-300/70">Mode C rules:</strong>&nbsp;
                No transliteration · No segmentation · No IndicF5+Parler split.
                English words may carry an Indic accent (expected — this is the experiment).
                Compare with Mode&nbsp;A &amp; Mode&nbsp;B panels above.
              </div>
            </section>
          )}
          {/* -- TEMPORARY MODE C SECTION END --------------------------------- */}

          {/* -- TEMPORARY MODE D SECTION START -------------------------------- */}
          {/* Mode D: Indic Parler Mixed TTS Isolated Test                       */}
          {/* REMOVE: this entire section after Mode D evaluation is complete   */}
          {_USE_INDIC_PARLER_MIXED_TTS_TEST && (
            <section className="glass-card rounded-3xl p-5 sm:p-6 flex flex-col gap-4 border border-dashed border-amber-400/30">

              {/* Section header */}
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-amber-300/80 flex items-center gap-2">
                    <span>&#127775;</span>
                    Mode D &mdash; Indic Parler Multilingual TTS (Experiment)
                  </p>
                  <p className="mt-1 text-xs text-white/35">
                    Original Tamil&#43;English mixed text &#8594; ONE ai4bharat/indic-parler-tts call &#8594; ONE speaker &#8594; ONE WAV.
                    No transliteration. No segmentation. No split. Not IndicF5. Not Parler Mini.
                  </p>
                  <p className="mt-1 text-[10px] text-amber-300/40">
                    Model: ai4bharat/indic-parler-tts &nbsp;&middot;&nbsp; Speaker: Jaya (Tamil female) &nbsp;&middot;&nbsp; GPU: A10G &nbsp;&middot;&nbsp; 44,100 Hz
                  </p>
                </div>
                <span className="shrink-0 rounded-full border border-amber-400/25 bg-amber-400/10 px-2 py-1 text-[10px] font-semibold text-amber-200/80">
                  DEV ONLY
                </span>
              </div>

              {/* Quick-fill test sentences */}
              <div className="flex flex-col gap-1.5">
                <span className="text-[10px] font-bold uppercase tracking-[0.10em] text-amber-300/50">
                  Quick-fill test sentences
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {_MODE_D_TEST_SENTENCES.map((s, i) => (
                    <button
                      key={i}
                      type="button"
                      id={`mode-d-sentence-${i + 1}`}
                      disabled={indicParlerMixedLoading}
                      onClick={() => setIndicParlerMixedText(s)}
                      className="text-[10px] bg-amber-500/10 hover:bg-amber-500/20 border border-amber-400/20 hover:border-amber-400/40 text-amber-200/70 px-2 py-1 rounded-lg transition-all disabled:opacity-40"
                    >
                      {i < 8 ? `Mixed ${i + 1}` : i === 8 ? 'Pure Tamil' : 'Pure English'}
                    </button>
                  ))}
                </div>
              </div>

              {/* Textarea */}
              <textarea
                id="indic-parler-mixed-tts-textarea"
                aria-label="Mode D Indic Parler Mixed TTS Test"
                value={indicParlerMixedText}
                onChange={(e) => setIndicParlerMixedText(e.target.value)}
                disabled={indicParlerMixedLoading}
                rows={4}
                placeholder={
                  'Paste Tamil+English mixed text here, for example:\n' +
                  'Artificial Intelligence  difficult topics-  simple  explain .'
                }
                className="w-full bg-white/[0.03] border border-amber-400/20 focus:border-amber-400/50 rounded-2xl px-4 py-3 text-sm text-white/90 leading-relaxed resize-none outline-none transition-all placeholder:text-white/20 disabled:opacity-60"
              />

              {/* Action row */}
              <div className="flex items-center gap-3 flex-wrap">
                <button
                  id="indic-parler-mixed-tts-generate-btn"
                  type="button"
                  onClick={handleIndicParlerMixedGenerate}
                  disabled={indicParlerMixedLoading || !indicParlerMixedText.trim()}
                  className="flex items-center gap-2 bg-amber-600/80 hover:bg-amber-600 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs font-semibold px-4 py-2 rounded-xl transition-all hover:scale-[1.03] active:scale-[0.97]"
                >
                  {indicParlerMixedLoading ? (
                    <>
                      <div className="w-3.5 h-3.5 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                      Generating&#8230;
                    </>
                  ) : (
                    <>&#127775; Generate (Mode D)</>
                  )}
                </button>

                {(indicParlerMixedAudioUrl || indicParlerMixedError) && !indicParlerMixedLoading && (
                  <button
                    id="indic-parler-mixed-tts-reset-btn"
                    type="button"
                    onClick={handleIndicParlerMixedReset}
                    className="text-xs text-white/35 hover:text-white/60 transition-colors"
                  >
                    Clear
                  </button>
                )}

                {indicParlerMixedLatencyMs !== null && !indicParlerMixedLoading && (
                  <span className="text-[11px] text-amber-300/60 font-mono">
                    {indicParlerMixedLatencyMs >= 1000
                      ? `${(indicParlerMixedLatencyMs / 1000).toFixed(1)}s`
                      : `${indicParlerMixedLatencyMs}ms`
                    } latency
                  </span>
                )}

                {indicParlerMixedSampleRate !== null && !indicParlerMixedLoading && (
                  <span className="text-[11px] text-amber-300/40 font-mono">
                    {indicParlerMixedSampleRate.toLocaleString()} Hz
                  </span>
                )}
              </div>

              {/* Loading status */}
              {indicParlerMixedLoading && (
                <div className="flex items-center gap-2.5 text-xs text-amber-300/70">
                  <div className="w-3.5 h-3.5 rounded-full border-2 border-amber-400/30 border-t-amber-400 animate-spin shrink-0" />
                  <span>
                    Sending raw mixed text to ai4bharat/indic-parler-tts&#8230; (first request may take ~120 s for cold-start)
                  </span>
                </div>
              )}

              {/* Hidden audio element */}
              {indicParlerMixedAudioUrl && (
                <audio
                  ref={indicParlerMixedAudioRef}
                  src={indicParlerMixedAudioUrl}
                  onEnded={() => setIndicParlerMixedPlaying(false)}
                  onPause={() => setIndicParlerMixedPlaying(false)}
                  onPlay={() => setIndicParlerMixedPlaying(true)}
                  preload="auto"
                  className="sr-only"
                />
              )}

              {/* Play / Pause controls */}
              {indicParlerMixedAudioUrl && !indicParlerMixedLoading && (
                <div className="flex items-center gap-3 bg-amber-500/8 border border-amber-500/20 rounded-xl px-4 py-2.5">
                  <button
                    id="indic-parler-mixed-tts-play-btn"
                    type="button"
                    onClick={() => {
                      const audio = indicParlerMixedAudioRef.current
                      if (!audio) return
                      if (indicParlerMixedPlaying) {
                        audio.pause()
                      } else {
                        audio.play()
                      }
                    }}
                    className="flex items-center gap-2 bg-amber-500/20 hover:bg-amber-500/30 border border-amber-400/30 text-amber-200 text-xs font-semibold px-3 py-1.5 rounded-lg transition-all hover:scale-[1.03] active:scale-[0.97]"
                  >
                    {indicParlerMixedPlaying ? (
                      <><PauseIcon />Pause</>
                    ) : (
                      <><PlayIcon />Play Audio</>
                    )}
                  </button>
                  <span className="text-[11px] text-amber-300/50">
                    Mode D &middot; indic-parler-tts &middot; speaker: {indicParlerMixedSpeaker ?? 'Jaya'} &middot; one model &middot; raw mixed text
                  </span>
                </div>
              )}

              {/* Error message */}
              {indicParlerMixedError && !indicParlerMixedLoading && (
                <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-xl px-3 py-2.5">
                  <span className="text-red-400 text-sm shrink-0">&#9888;</span>
                  <p className="text-xs text-red-400">{indicParlerMixedError}</p>
                </div>
              )}

              {/* Info box - Mode D description */}
              <div className="bg-amber-500/5 border border-amber-500/15 rounded-xl px-3 py-2.5 text-[11px] text-amber-300/50 leading-relaxed">
                <strong className="text-amber-300/70">Mode D rules:</strong>&nbsp;
                No transliteration &middot; No segmentation &middot; Not IndicF5 &middot; Not Parler Mini v1.
                Uses ai4bharat/indic-parler-tts &mdash; a unified multilingual model with description-conditioned voice.
                Compare with Mode&nbsp;A, Mode&nbsp;B &amp; Mode&nbsp;C panels above.
              </div>
            </section>
          )}
          {/* -- TEMPORARY MODE D SECTION END ---------------------------------- */}

          {/* ── TEMPORARY: Sinhala TTS Test Panel ─────────────────────────────
               Model: dialoglk/SinhalaVITS-TTS-F1 (Nipunika female, 22,050 Hz)
               NOT connected to ASR / RAG / any production route.
               REMOVE after Sinhala TTS evaluation is complete.
          ── */}
          {_USE_SINHALA_TTS_TEST && (
            <section
              id="sinhala-vits-tts-panel"
              className="glass-card rounded-3xl p-5 sm:p-6 flex flex-col gap-4 border border-emerald-600/20"
            >
              {/* Header */}
              <div className="flex items-start justify-between gap-3">
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">🇱🇰</span>
                    <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-emerald-400/70">
                      Sinhala TTS — SinhalaVITS F1 (Temporary Test)
                    </p>
                  </div>
                  <p className="text-[11px] text-white/30 pl-7">
                    dialoglk/SinhalaVITS-TTS-F1 · Nipunika female · Coqui VITS · 22,050 Hz
                  </p>
                </div>
                <span className="shrink-0 inline-flex items-center gap-1 bg-red-500/10 border border-red-500/20 text-red-400/80 text-[9px] font-bold uppercase tracking-wide rounded-full px-2 py-0.5">
                  DEV ONLY
                </span>
              </div>

              {/* Not-connected-to-RAG warning */}
              <div className="flex items-center gap-2 bg-amber-500/5 border border-amber-500/15 rounded-xl px-3 py-2">
                <span className="text-amber-400 text-xs shrink-0">⚠️</span>
                <p className="text-[11px] text-amber-300/50">
                  Manual test only — not connected to ASR, RAG, or any production route.
                  English words pass through the romanizer unchanged; pronunciation quality is unknown.
                </p>
              </div>

              {/* Quick-fill test sentences */}
              <div className="flex flex-col gap-1.5">
                <span className="text-[10px] font-bold uppercase tracking-[0.10em] text-emerald-300/50">
                  Quick-fill test cases
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {_SINHALA_TEST_SENTENCES.map((s, i) => (
                    <button
                      key={i}
                      type="button"
                      id={`sinhala-tts-sentence-${i + 1}`}
                      disabled={sinhalaTtsLoading}
                      onClick={() => setSinhalaTtsText(s)}
                      className="text-[10px] bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-400/20 hover:border-emerald-400/40 text-emerald-200/70 px-2 py-1 rounded-lg transition-all disabled:opacity-40"
                    >
                      {i === 0 ? 'Test 1 — Pure Sinhala'
                        : i === 1 ? 'Test 2 — Mixed (Sinhala + EN)'
                        : i === 2 ? 'Test 3 — Dogs (EN names)'
                        : 'Test 4 — More English'}
                    </button>
                  ))}
                </div>
              </div>

              {/* Textarea */}
              <textarea
                id="sinhala-tts-textarea"
                aria-label="Sinhala TTS test input"
                value={sinhalaTtsText}
                onChange={(e) => setSinhalaTtsText(e.target.value)}
                disabled={sinhalaTtsLoading}
                rows={4}
                placeholder={'Paste Sinhala text here, e.g.: සිංහල භාෂාව ශ්‍රී ලංකාවේ ප්‍රධාන භාෂාවකි.'}
                className="w-full bg-white/[0.03] border border-emerald-400/20 focus:border-emerald-400/50 rounded-2xl px-4 py-3 text-sm text-white/90 leading-relaxed resize-none outline-none transition-all placeholder:text-white/20 disabled:opacity-60"
              />

              {/* Action row */}
              <div className="flex items-center gap-3 flex-wrap">
                <button
                  id="sinhala-tts-generate-btn"
                  type="button"
                  onClick={handleSinhalaTtsGenerate}
                  disabled={sinhalaTtsLoading || !sinhalaTtsText.trim()}
                  className="flex items-center gap-2 bg-emerald-700/80 hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs font-semibold px-4 py-2 rounded-xl transition-all hover:scale-[1.03] active:scale-[0.97]"
                >
                  {sinhalaTtsLoading ? (
                    <>
                      <div className="w-3.5 h-3.5 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                      Generating&#8230;
                    </>
                  ) : (
                    <>&#127908; Generate Sinhala Speech</>
                  )}
                </button>

                {(sinhalaTtsAudioUrl || sinhalaTtsError) && !sinhalaTtsLoading && (
                  <button
                    id="sinhala-tts-reset-btn"
                    type="button"
                    onClick={handleSinhalaTtsReset}
                    className="text-xs text-white/35 hover:text-white/60 transition-colors"
                  >
                    Clear
                  </button>
                )}

                {sinhalaTtsLatencyMs !== null && !sinhalaTtsLoading && (
                  <span className="text-[11px] text-emerald-300/60 font-mono">
                    {sinhalaTtsLatencyMs >= 1000
                      ? `${(sinhalaTtsLatencyMs / 1000).toFixed(1)}s`
                      : `${sinhalaTtsLatencyMs}ms`
                    } latency
                  </span>
                )}

                {sinhalaTtsSampleRate !== null && !sinhalaTtsLoading && (
                  <span className="text-[11px] text-emerald-300/40 font-mono">
                    {sinhalaTtsSampleRate.toLocaleString()} Hz
                  </span>
                )}
              </div>

              {/* Loading status */}
              {sinhalaTtsLoading && (
                <div className="flex items-center gap-2.5 text-xs text-emerald-300/70">
                  <div className="w-3.5 h-3.5 rounded-full border-2 border-emerald-400/30 border-t-emerald-400 animate-spin shrink-0" />
                  <span>
                    Sending to SinhalaVITS-TTS-F1&#8230; (first request: ~60-90 s cold-start)
                  </span>
                </div>
              )}

              {/* ── ROMANIZER DEBUG PREVIEW ──────────────────────────────── */}
              {(sinhalaTtsText.trim() && (sinhalaRomanized !== null || sinhalaRomanizeLoading)) && (
                <div className="flex flex-col gap-1.5 bg-white/[0.02] border border-emerald-400/10 rounded-xl px-3 py-3">
                  <span className="text-[10px] font-bold uppercase tracking-[0.10em] text-emerald-300/50">
                    🔤 Romanizer Debug Preview
                  </span>
                  <div className="grid grid-cols-1 gap-2 text-[11px]">
                    <div>
                      <span className="text-white/25 font-semibold">Original input:</span>
                      <p className="text-white/50 font-mono mt-0.5 break-all leading-relaxed">
                        &quot;{sinhalaTtsText.trim()}&quot;
                      </p>
                    </div>
                    {sinhalaMixedPhonetics && sinhalaPhoneticPreview && (
                      <div>
                        <span className="text-emerald-300/50 font-semibold">Phonetic TTS copy:</span>
                        <p className="text-emerald-100/70 font-mono mt-0.5 break-all leading-relaxed">&quot;{sinhalaPhoneticPreview.phonetic_text}&quot;</p>
                        {sinhalaPhoneticPreview.spans.map((span, i) => (
                          <p key={`${span.original}-${i}`} className="text-white/35 mt-1">{span.original} → {span.source} → {span.phonetic}</p>
                        ))}
                        {sinhalaPhoneticPreview.warnings.map((warning) => <p key={warning} className="text-amber-300/70 mt-1">⚠ {warning}</p>)}
                      </div>
                    )}
                    <div>
                      <span className="text-emerald-300/50 font-semibold">Romanized input sent to VITS:</span>
                      {sinhalaRomanizeLoading ? (
                        <p className="text-white/30 mt-0.5 italic">Computing&#8230;</p>
                      ) : (
                        <p className="text-emerald-200/60 font-mono mt-0.5 break-all leading-relaxed">
                          &quot;{sinhalaRomanized}&quot;
                        </p>
                      )}
                    </div>
                  </div>
                  <p className="text-[10px] text-white/20 mt-1">
                    Note: English/Latin words pass through the romanizer unchanged.
                    Sinhala Unicode is converted to romanized Sinhala phonetics.
                  </p>
                </div>
              )}
              {/* ── END ROMANIZER DEBUG PREVIEW ───────────────────────────── */}

              {/* Hidden audio element */}
              {sinhalaTtsAudioUrl && (
                <audio
                  ref={sinhalaTtsAudioRef}
                  src={sinhalaTtsAudioUrl}
                  onEnded={() => setSinhalaTtsPlaying(false)}
                  onPause={() => setSinhalaTtsPlaying(false)}
                  onPlay={() => setSinhalaTtsPlaying(true)}
                  preload="auto"
                  className="sr-only"
                />
              )}

              {/* Play / Pause controls */}
              {sinhalaTtsAudioUrl && !sinhalaTtsLoading && (
                <div className="flex items-center gap-3 bg-emerald-500/8 border border-emerald-500/20 rounded-xl px-4 py-2.5">
                  <button
                    id="sinhala-tts-play-btn"
                    type="button"
                    onClick={() => {
                      const audio = sinhalaTtsAudioRef.current
                      if (!audio) return
                      if (sinhalaTtsPlaying) {
                        audio.pause()
                      } else {
                        audio.play()
                      }
                    }}
                    className="flex items-center gap-2 bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-400/30 text-emerald-200 text-xs font-semibold px-3 py-1.5 rounded-lg transition-all hover:scale-[1.03] active:scale-[0.97]"
                  >
                    {sinhalaTtsPlaying ? (
                      <><PauseIcon />Pause</>
                    ) : (
                      <><PlayIcon />Play Audio</>
                    )}
                  </button>
                  <span className="text-[11px] text-emerald-300/50">
                    SinhalaVITS-F1 &middot; Nipunika female &middot; Coqui VITS &middot; 22,050 Hz
                  </span>
                </div>
              )}

              {/* Error message */}
              {sinhalaTtsError && !sinhalaTtsLoading && (
                <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-xl px-3 py-2.5">
                  <span className="text-red-400 text-sm shrink-0">&#9888;</span>
                  <p className="text-xs text-red-400">{sinhalaTtsError}</p>
                </div>
              )}

              {/* Info box */}
              <div className="bg-emerald-500/5 border border-emerald-500/15 rounded-xl px-3 py-2.5 text-[11px] text-emerald-300/50 leading-relaxed">
                <strong className="text-emerald-300/70">Isolation:</strong>&nbsp;
                Not connected to RAG &middot; Not connected to ASR &middot; Manual textarea only.
                English words in Sinhala text are passed as-is to VITS — pronunciation quality is an open evaluation question.
                Use the romanizer preview above to inspect how each word is handled.
              </div>
            </section>
          )}
          {/* ── TEMPORARY SINHALA TTS TEST SECTION END ──────────────────── */}

          {/* -- TEMPORARY: Sinhala ASR Test Panel ---------------------------------
               Model: Lingalingeswaran/whisper-small-sinhala
               Isolated: file-upload only, no RAG, no TTS, no transcript correction.
               REMOVE after Sinhala ASR evaluation is complete.
          --------------------------------------------------------------------- */}
          {_USE_SINHALA_ASR_TEST && (
            <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-6 space-y-5">
              {/* Header */}
              <div className="flex items-center justify-between flex-wrap gap-3">
                <div>
                  <h2 className="text-base font-bold text-white/90 tracking-tight">
                    &#127908; Sinhala ASR &mdash; Whisper Small Sinhala
                    <span className="ml-2 text-[10px] font-semibold uppercase tracking-widest text-amber-400/70 border border-amber-400/20 bg-amber-400/10 rounded-full px-2 py-0.5">Temporary Test</span>
                  </h2>
                  <p className="text-[11px] text-white/40 mt-0.5">
                    Lingalingeswaran/whisper-small-sinhala &middot; Apache 2.0 &middot; T4 GPU &middot; No RAG &middot; No TTS
                  </p>
                </div>
                <button
                  id="sinhala-asr-clear-btn"
                  onClick={() => {
                    setSinhalaAsrFile(null)
                    setSinhalaAsrTranscript(null)
                    setSinhalaAsrError(null)
                    setSinhalaAsrLatencyMs(null)
                    setSinhalaAsrElapsed(0)
                    if (sinhalaAsrFileInputRef.current) sinhalaAsrFileInputRef.current.value = ''
                  }}
                  className="text-[11px] text-white/30 hover:text-white/60 transition-colors border border-white/10 rounded-lg px-3 py-1.5"
                >
                  Clear / Reset
                </button>
              </div>

              {/* File upload */}
              <div className="space-y-2">
                <label className="text-[11px] font-semibold uppercase tracking-widest text-white/40">Audio File</label>
                <div className="flex items-center gap-3 flex-wrap">
                  <label
                    htmlFor="sinhala-asr-file-input"
                    className="cursor-pointer inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 transition-colors text-sm text-white/70"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="17 8 12 3 7 8" />
                      <line x1="12" y1="3" x2="12" y2="15" />
                    </svg>
                    Choose Audio File
                  </label>
                  <input
                    id="sinhala-asr-file-input"
                    ref={sinhalaAsrFileInputRef}
                    type="file"
                    accept="audio/wav,audio/mp3,audio/mpeg,audio/mp4,audio/x-m4a,audio/webm,audio/ogg"
                    className="sr-only"
                    onChange={(e) => {
                      const file = e.target.files?.[0] ?? null
                      setSinhalaAsrFile(file)
                      setSinhalaAsrTranscript(null)
                      setSinhalaAsrError(null)
                      setSinhalaAsrLatencyMs(null)
                    }}
                  />
                  {sinhalaAsrFile ? (
                    <span className="text-[12px] text-emerald-400/80 font-medium truncate max-w-[220px]">
                      &#128204; {sinhalaAsrFile.name}
                    </span>
                  ) : (
                    <span className="text-[11px] text-white/25 italic">No file selected &mdash; WAV / MP3 / M4A / WebM</span>
                  )}
                </div>
              </div>

              {/* Test sentences reference */}
              <div className="space-y-1.5">
                <label className="text-[11px] font-semibold uppercase tracking-widest text-white/40">Reference Test Sentences</label>
                <div className="flex flex-col gap-1.5">
                  {[
                    '\u0db8\u0db8 \u0d85\u0daf \u0db4\u0dcf\u0dc3\u0dbd\u0da7 \u0d9c\u0dd2\u0dba\u0dcf.',
                    '\u0dc3\u0dd2\u0d82\u0dc4\u0dbd \u0db7\u0dcf\u0dc2\u0dcf\u0dc0 \u0dc1\u0dca\u200d\u0dbb\u0dd3 \u0dbd\u0d82\u0d9a\u0dcf\u0dc0\u0dda \u0db4\u0dca\u200d\u0dbb\u0db0\u0dcf\u0db1 \u0db7\u0dcf\u0dc2\u0dcf\u0dc0\u0d9a\u0dca.',
                    '\u0d85\u0daf \u0d9a\u0dcf\u0dbd\u0d9c\u0dd4\u0dab\u0dba \u0d89\u0dad\u0dcf \u0dc4\u0ddc\u0db3\u0dba\u0dd2.',
                    '\u0d85\u0db0\u0dca\u200d\u0dba\u0dcf\u0db4\u0db1\u0dba \u0dc3\u0db3\u0dc4\u0dcf \u0db1\u0dc0 \u0dad\u0dcf\u0d9a\u0dca\u0dc2\u0dab\u0dd2\u0d9a \u0db8\u0dd9\u0dc0\u0dbd\u0db8\u0dca \u0db7\u0dcf\u0dc0\u0dd2\u0dad\u0dcf \u0d9a\u0dd2\u0dbb\u0dd3\u0db8\u0dd9\u0db1\u0dca \u0dc3\u0dd2\u0dc3\u0dd4\u0db1\u0dca\u0da7 \u0d89\u0d9c\u0dd9\u0db1 \u0d9a\u0dd2\u0db8 \u0db4\u0dc4\u0dc3\u0dd4 \u0dc0\u0dd9\u0db1\u0dc0\u0dcf.',
                    '\u0d85\u0daf \u0d85\u0db4\u0dd2 Artificial Intelligence \u0d9c\u0dd0\u0db1 \u0d89\u0d9c\u0dd9\u0db1 \u0d9c\u0dad\u0dca\u0dad\u0dcf.',
                  ].map((sentence, i) => (
                    <div key={i} className="flex items-start gap-2 text-[12px]">
                      <span className="text-white/25 font-mono shrink-0">T{i+1}.</span>
                      <span
                        className="text-white/60 select-all leading-relaxed"
                        style={{ fontFamily: "'Noto Sans Sinhala', 'Iskoola Pota', sans-serif" }}
                      >
                        {sentence}
                      </span>
                    </div>
                  ))}
                </div>
                <p className="text-[10px] text-white/25 italic">Record any sentence with your mic app, save as WAV/MP3, then upload above.</p>
              </div>

              {/* Transcribe button + elapsed */}
              <div className="flex items-center gap-4 flex-wrap">
                <button
                  id="sinhala-asr-transcribe-btn"
                  disabled={!sinhalaAsrFile || sinhalaAsrLoading}
                  onClick={async () => {
                    if (!sinhalaAsrFile) return
                    setSinhalaAsrLoading(true)
                    setSinhalaAsrTranscript(null)
                    setSinhalaAsrError(null)
                    setSinhalaAsrLatencyMs(null)
                    setSinhalaAsrElapsed(0)
                    const t0 = Date.now()
                    if (sinhalaAsrTimerRef.current) clearInterval(sinhalaAsrTimerRef.current)
                    sinhalaAsrTimerRef.current = setInterval(() => {
                      setSinhalaAsrElapsed(Math.round((Date.now() - t0) / 1000))
                    }, 1000)
                    try {
                      const res = await testSinhalaASR(sinhalaAsrFile)
                      setSinhalaAsrTranscript(res.transcript)
                      setSinhalaAsrLatencyMs(res.latency_ms)
                    } catch (err: unknown) {
                      setSinhalaAsrError(err instanceof Error ? err.message : 'Sinhala ASR failed - check Modal logs.')
                    } finally {
                      setSinhalaAsrLoading(false)
                      if (sinhalaAsrTimerRef.current) { clearInterval(sinhalaAsrTimerRef.current); sinhalaAsrTimerRef.current = null }
                    }
                  }}
                  className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-xl font-semibold text-sm transition-all ${
                    sinhalaAsrLoading
                      ? 'bg-white/10 text-white/40 cursor-not-allowed'
                      : sinhalaAsrFile
                        ? 'bg-gradient-to-r from-amber-500 to-orange-500 text-white shadow-lg hover:opacity-90 active:scale-95'
                        : 'bg-white/5 text-white/20 cursor-not-allowed border border-white/10'
                  }`}
                >
                  {sinhalaAsrLoading ? (
                    <>
                      <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
                      </svg>
                      Transcribing&hellip;
                    </>
                  ) : '&#127908; Transcribe'}
                </button>

                {sinhalaAsrLoading && (
                  <span className="text-[12px] text-white/40 tabular-nums">
                    {sinhalaAsrElapsed}s elapsed &mdash; T4 cold-start ~60-90 s
                  </span>
                )}

                {sinhalaAsrLatencyMs !== null && !sinhalaAsrLoading && (
                  <span className="text-[11px] text-emerald-400/70 font-medium">
                    &#9889; {sinhalaAsrLatencyMs.toLocaleString()} ms
                  </span>
                )}
              </div>

              {/* Transcript output */}
              {sinhalaAsrTranscript !== null && (
                <div className="space-y-2">
                  <label className="text-[11px] font-semibold uppercase tracking-widest text-white/40">Sinhala Transcript</label>
                  <div
                    id="sinhala-asr-transcript-output"
                    className="w-full min-h-[80px] rounded-xl border border-white/10 bg-black/30 px-4 py-3 text-base leading-relaxed text-white/90 select-all"
                    style={{ fontFamily: "'Noto Sans Sinhala', 'Iskoola Pota', sans-serif" }}
                  >
                    {sinhalaAsrTranscript || <span className="text-white/25 italic text-sm">(empty transcript)</span>}
                  </div>
                  <p className="text-[10px] text-white/25">
                    Raw ASR output &mdash; no correction, no RAG, no TTS. Evaluate Sinhala character accuracy directly.
                  </p>
                </div>
              )}

              {/* Error display */}
              {sinhalaAsrError && (
                <div className="rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">
                  <strong>Error:</strong> {sinhalaAsrError}
                </div>
              )}

              {/* Isolation note */}
              <div className="text-[11px] text-white/25 border-t border-white/5 pt-3">
                <strong className="text-amber-300/60">Isolation:</strong>&nbsp;
                File upload only &middot; No microphone hook &middot; No RAG &middot; No TTS &middot; No transcript correction.
                Evaluating raw <code className="text-white/40">Lingalingeswaran/whisper-small-sinhala</code> checkpoint.
              </div>
            </section>
          )}
          {/* -- TEMPORARY SINHALA ASR TEST SECTION END -- */}
          {/* ── Footer ────────────────────────────────────────── */}
          <div className="flex flex-wrap justify-center gap-x-5 gap-y-1.5 pt-2 text-[11px] text-white/20 font-medium">
            <span>{language === 'tamil' ? 'Tamil ASR Qwen3' : 'Whisper Large V3'}</span>
            <span className="text-white/10">·</span>
            <span>Gemma 4 12B Transcript Corrector</span>
            <span className="text-white/10">·</span>
            <span>Gemma 4 12B RAG</span>
            <span className="text-white/10">·</span>
            <span>Modal.com</span>
          </div>

        </div>
      </main>
    </div>
  )
}

// ─────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────

function SectionLabel({ icon, text }: { icon: string; text: string }) {
  return (
    <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-white/30 mb-4 flex items-center gap-2">
      <span>{icon}</span>
      {text}
    </p>
  )
}

function StepBadge({ n, done }: { n: number; done: boolean }) {
  return (
    <span
      className={`inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold shrink-0 transition-all duration-300 ${
        done
          ? 'bg-brand-500 text-white shadow-brand'
          : 'bg-white/10 text-white/40'
      }`}
    >
      {done ? '✓' : n}
    </span>
  )
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round"
      className={`text-white/30 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  )
}

function DocRow({ doc, onDelete }: { doc: DocumentItem; onDelete: (id: string) => void }) {
  const [deleting, setDeleting] = useState(false)
  const EXT_ICONS: Record<string, string> = {
    pdf: '📕', pptx: '📊', docx: '📝', xlsx: '📗', txt: '📄', md: '📋',
  }
  const icon = EXT_ICONS[doc.file_type] ?? '📄'

  const handleDelete = async () => {
    setDeleting(true)
    await onDelete(doc.document_id)
    setDeleting(false)
  }

  return (
    <li className="flex items-center gap-3 bg-white/[0.02] border border-white/[0.07] rounded-xl px-3 py-2.5 group">
      <span className="text-base shrink-0">{icon}</span>
      <div className="flex flex-col min-w-0 flex-1">
        <span className="text-[13px] font-medium text-white/80 truncate">{doc.filename}</span>
        <span className="text-[11px] text-white/30">{doc.chunk_count} chunks indexed</span>
      </div>
      <button
        type="button"
        onClick={handleDelete}
        disabled={deleting}
        aria-label={`Delete ${doc.filename}`}
        className="opacity-0 group-hover:opacity-100 text-white/25 hover:text-red-400 transition-all disabled:opacity-30 p-1 rounded-lg hover:bg-red-500/10"
      >
        {deleting ? (
          <div className="w-3.5 h-3.5 rounded-full border border-white/30 border-t-white animate-spin" />
        ) : (
          <TrashIcon />
        )}
      </button>
    </li>
  )
}

function TrashIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6l-1 14H6L5 6" />
      <path d="M10 11v6M14 11v6" />
      <path d="M9 6V4h6v2" />
    </svg>
  )
}

function Chip({ label, value, variant }: {
  label: string
  value: string
  variant: 'brand' | 'accent' | 'dim'
}) {
  const cls = {
    brand:  'border-brand-500/30  bg-brand-500/10  text-brand-300',
    accent: 'border-accent-500/30 bg-accent-500/10 text-accent-300',
    dim:    'border-white/10      bg-white/5       text-white/50',
  }[variant]

  return (
    <span className={`inline-flex items-center gap-1.5 border rounded-full px-2.5 py-1 text-[11px] font-semibold ${cls}`}>
      <span className="opacity-60 font-normal">{label}:</span>
      <span>{value}</span>
    </span>
  )
}

function PlayIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
      <polygon points="5 3 19 12 5 21 5 3" />
    </svg>
  )
}

function PauseIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
      <rect x="6" y="4" width="4" height="16" rx="1" />
      <rect x="14" y="4" width="4" height="16" rx="1" />
    </svg>
  )
}
