import React from 'react';
import { colors, fonts } from './theme';
export type Upload = { name: string; file: File };
export default function FilePicker({ accept, onPick, disabled }: { accept: string; onPick: (file: Upload) => void; disabled?: boolean }) {
  return <input aria-label="Choose a study file" disabled={disabled} type="file" accept={accept} style={{ padding: 18, border: `1px dashed ${colors.line}`, borderRadius: 8, background: colors.bg, width: '100%', boxSizing: 'border-box', color: colors.muted, fontFamily: fonts.body, opacity: disabled ? 0.5 : 1 }} onChange={e => { const file = e.target.files?.[0]; if (file && !disabled) onPick({ name: file.name, file }); e.target.value = ''; }} />;
}
