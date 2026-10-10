import React from 'react';
export type Upload = { name: string; file: File };
export default function FilePicker({ accept, onPick, disabled }: { accept: string; onPick: (file: Upload) => void; disabled?: boolean }) {
  return <input aria-label="Choose a study file" disabled={disabled} type="file" accept={accept} style={{ padding: 18, border: '1px dashed #C9BCAE', borderRadius: 12, background: '#FFFFFF80', width: '100%', boxSizing: 'border-box', color: '#77736A', fontFamily: 'inherit', opacity: disabled ? 0.5 : 1 }} onChange={e => { const file = e.target.files?.[0]; if (file && !disabled) onPick({ name: file.name, file }); e.target.value = ''; }} />;
}
