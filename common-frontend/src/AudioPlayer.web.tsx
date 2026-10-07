import React, { useEffect, useState } from 'react';
export default function AudioPlayer({ blob }: { blob: Blob }) {
  const [url, setUrl] = useState('');
  useEffect(() => { const next = URL.createObjectURL(blob); setUrl(next); return () => URL.revokeObjectURL(next); }, [blob]);
  return url ? <audio controls src={url} style={{ width: '100%' }} aria-label="Spoken tutor answer" /> : null;
}
