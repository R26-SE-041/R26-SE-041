import React, { useState } from 'react';
import { View } from 'react-native';
import { Button, Notice, styles } from './ui';
export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob), link = document.createElement('a');
  link.href = url; link.download = filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export default function OutputActions({ text, name = 'study-notes', image, mime = 'image/png' }: { text?: string; name?: string; image?: string; mime?: string }) {
  const [message, setMessage] = useState(''), [error, setError] = useState('');
  return <View style={{ gap: 10 }}><View style={styles.row}>{!!text && <><Button secondary label="Copy text" onPress={async () => { setError(''); try { await navigator.clipboard.writeText(text); setMessage('Text copied.'); } catch { setError('Clipboard access is unavailable. Select the text to copy it.'); } }} /><Button secondary label="Download text" onPress={() => downloadBlob(new Blob([text], { type: 'text/plain;charset=utf-8' }), `${name}.txt`)} /></>}{!!image && <Button secondary label="Download image" onPress={() => { const link = document.createElement('a'); link.href = `data:${mime};base64,${image}`; link.download = `${name}.${mime.split('/')[1] || 'png'}`; link.click(); }} />}</View><Notice text={message} /><Notice text={error} error /></View>;
}
