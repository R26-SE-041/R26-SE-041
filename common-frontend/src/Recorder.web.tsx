import React, { useEffect, useRef, useState } from 'react';
import { View } from 'react-native';
import { Button, Notice } from './ui';
import type { Upload } from './FilePicker';
export default function Recorder({ onRecorded, disabled }: { onRecorded: (file: Upload) => void; disabled?: boolean }) {
  const [recording, setRecording] = useState(false), [error, setError] = useState('');
  const recorder = useRef<MediaRecorder | null>(null), stream = useRef<MediaStream | null>(null), mounted = useRef(true), limit = useRef<ReturnType<typeof setTimeout> | null>(null);
  const release = () => { stream.current?.getTracks().forEach(track => track.stop()); stream.current = null; if (limit.current) clearTimeout(limit.current); };
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; if (recorder.current?.state === 'recording') recorder.current.stop(); release(); }; }, []);
  const start = async () => {
    setError('');
    try {
      if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') throw new Error('Microphone recording is unavailable in this browser. Upload an audio file instead.');
      const media = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!mounted.current) { media.getTracks().forEach(track => track.stop()); return; }
      stream.current = media;
      const mime = ['audio/webm', 'audio/mp4', 'audio/ogg'].find(value => MediaRecorder.isTypeSupported(value));
      const capture = new MediaRecorder(media, mime ? { mimeType: mime } : undefined); const chunks: Blob[] = [];
      recorder.current = capture;
      capture.ondataavailable = event => { if (event.data.size) chunks.push(event.data); };
      capture.onstop = () => { release(); if (mounted.current) { setRecording(false); const type = capture.mimeType.split(';')[0] || 'audio/webm'; const suffix = type === 'audio/mp4' ? 'm4a' : type === 'audio/ogg' ? 'ogg' : 'webm'; const file = new File(chunks, `voice-question.${suffix}`, { type }); if (file.size) onRecorded({ name: file.name, file }); } };
      capture.onerror = () => { release(); if (mounted.current) { setRecording(false); setError('Recording failed. Please upload an audio file.'); } };
      capture.start(); setRecording(true); limit.current = setTimeout(() => { if (capture.state === 'recording') capture.stop(); }, 120000);
    } catch (e) { release(); setError(e instanceof Error ? e.message : 'Microphone access failed.'); }
  };
  return <View style={{ gap: 12 }}><Button label={recording ? 'Stop & transcribe' : 'Record a voice question'} secondary disabled={disabled && !recording} onPress={recording ? () => recorder.current?.stop() : start} />{recording && <Notice text="Recording… Stop when you have finished your question. Maximum two minutes." />}<Notice text={error} error /></View>;
}
