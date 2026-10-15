import { useEffect, useRef, useState } from 'react'

interface RecognitionResult { isFinal: boolean; 0: { transcript: string } }
interface Recognition {
  lang: string; continuous: boolean; interimResults: boolean; maxAlternatives: number
  onstart: (() => void) | null; onend: (() => void) | null
  onerror: ((event: { error: string }) => void) | null
  onresult: ((event: { resultIndex: number; results: ArrayLike<RecognitionResult> }) => void) | null
  start(): void; abort(): void
}
type RecognitionConstructor = new () => Recognition
export const isAndroidBrowser = () => /Android/i.test(navigator.userAgent)
function recognitionConstructor(): RecognitionConstructor | undefined {
  const browser = window as unknown as { SpeechRecognition?: RecognitionConstructor; webkitSpeechRecognition?: RecognitionConstructor }
  return browser.SpeechRecognition || browser.webkitSpeechRecognition
}

/** No Modal calls. Browser recognition can use its provider's online service. */
export function useHandsFreeRecognition(active: boolean, suspended: boolean, onText: (text: string) => void, playbackInterruptions = 0) {
  const [enabled, setEnabled] = useState(false)
  const [listening, setListening] = useState(false)
  const [error, setError] = useState('')
  const callback = useRef(onText)
  callback.current = onText
  const supported = Boolean(recognitionConstructor())
  useEffect(() => { if (!active) setEnabled(false) }, [active])
  useEffect(() => {
    if (!playbackInterruptions) return
    setEnabled(false)
    setError('Playback was interrupted outside a voice command. Hands-free is now off to avoid microphone/playback conflicts. Press Play to continue normally. Continuous voice control may not work alongside audio in this Android browser.')
  }, [playbackInterruptions])
  useEffect(() => {
    const hide = () => { if (document.visibilityState !== 'visible') setEnabled(false) }
    const pageHide = () => setEnabled(false)
    document.addEventListener('visibilitychange', hide)
    window.addEventListener('pagehide', pageHide)
    return () => { document.removeEventListener('visibilitychange', hide); window.removeEventListener('pagehide', pageHide) }
  }, [])
  useEffect(() => {
    if (!enabled || !active || suspended) { setListening(false); return }
    const Constructor = recognitionConstructor()
    if (!Constructor) return
    let alive = true, recognition: Recognition | null = null, timer: ReturnType<typeof setTimeout> | undefined
    let rapidEnds = 0, started = 0
    const stopWithError = (message: string) => {
      if (!alive) return
      alive = false; clearTimeout(timer); setListening(false); setEnabled(false); setError(message)
      if (recognition) { recognition.onresult = null; recognition.onend = null; (() => { try { recognition?.abort() } catch { /* Already ended. */ } })() }
    }
    const start = () => {
      if (!alive) return
      const instance = new Constructor()
      recognition = instance
      const seen = new Set<number>()
      instance.lang = 'en-US'; instance.continuous = true; instance.interimResults = false; instance.maxAlternatives = 1
      instance.onstart = () => { if (alive && recognition === instance) { started = Date.now(); setListening(true); setError('') } }
      instance.onresult = event => {
        if (!alive || recognition !== instance) return
        for (let index = event.resultIndex; index < event.results.length; index++) {
          const result = event.results[index]
          if (result.isFinal && !seen.has(index)) { seen.add(index); callback.current(result[0].transcript) }
        }
      }
      instance.onerror = event => {
        if (!alive || recognition !== instance || event.error === 'no-speech') return
        const messages: Record<string, string> = {
          'not-allowed': 'Microphone permission was denied. Allow microphone access, then enable hands-free again.',
          'service-not-allowed': 'Speech recognition is unavailable in this browser. Use the player controls.',
          'audio-capture': 'The microphone is unavailable or in use by another app.',
          network: 'Speech recognition lost its connection. Check your connection and enable hands-free again.',
          'language-not-supported': 'English voice recognition is unavailable in this browser.',
        }
        stopWithError(messages[event.error] || 'Voice listening stopped. Enable hands-free again to retry.')
      }
      instance.onend = () => {
        if (!alive || recognition !== instance) return
        instance.onresult = null; instance.onstart = null; instance.onerror = null; instance.onend = null; setListening(false)
        // Android recognizers can take audio focus each time they start. Never reacquire it
        // automatically after silence or a result: that can pause/resume media repeatedly.
        if (isAndroidBrowser()) {
          stopWithError('Your Android browser ended voice listening. Hands-free is off; it will not restart automatically or change playback. You can enable it again, but if audio is interrupted, use the player controls.')
          return
        }
        rapidEnds = Date.now() - started < 1500 ? rapidEnds + 1 : 0
        if (rapidEnds >= 3) { stopWithError('The browser repeatedly stopped listening. Enable hands-free again or use the player controls.'); return }
        timer = setTimeout(start, 400 + rapidEnds * 300)
      }
      started = Date.now()
      try { instance.start() } catch { stopWithError('Could not start voice recognition. Check microphone access and try again.') }
    }
    start()
    return () => {
      alive = false; clearTimeout(timer); setListening(false)
      if (recognition) { recognition.onresult = null; recognition.onend = null; recognition.onerror = null; recognition.onstart = null; (() => { try { recognition?.abort() } catch { /* Already ended. */ } })() }
    }
  }, [enabled, active, suspended])
  return { supported, enabled, listening, error,
    enable: () => { setError(''); if (supported) setEnabled(true) },
    disable: () => setEnabled(false) }
}
