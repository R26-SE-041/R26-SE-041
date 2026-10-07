import React from 'react';
import { Linking, Text, View } from 'react-native';
import { colors, styles } from './ui';
export function ResourceLink({ url, label }: { url: string; label: string }) {
  let valid = false; try { valid = ['http:', 'https:'].includes(new URL(url).protocol); } catch { /* Render unsafe URLs as text. */ }
  return <Text accessibilityRole={valid ? 'link' : undefined} onPress={valid ? () => { void Linking.openURL(url).catch(() => {}); } : undefined} style={{ color: valid ? colors.accent : colors.muted, lineHeight: 24 }}>{label}{valid ? ' ↗' : ''}</Text>;
}
export default function Markdown({ text }: { text: string }) {
  return <View style={{ gap: 8 }}>{text.split('\n').map((line, i) => {
    const heading = /^#{1,6}\s/.test(line);
    return <Text selectable key={i} style={heading ? styles.heading : styles.body}>{line.replace(/^#{1,6}\s/, '').split(/(\*\*[^*]+\*\*|\[[^\]]+\]\(https?:\/\/[^)]+\))/g).map((part,j) => {
      const link = /^\[([^\]]+)\]\((https?:\/\/[^)]+)\)$/.exec(part);
      if (link) return <ResourceLink key={j} label={link[1]} url={link[2]} />;
      return <Text key={j} style={part.startsWith('**') ? { fontWeight: '600' } : undefined}>{part.startsWith('**') ? part.slice(2,-2) : part}</Text>;
    })}</Text>;
  })}</View>;
}
