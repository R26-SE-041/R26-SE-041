import React from 'react';
import { ActivityIndicator, Platform, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
export const colors = { bg: '#F6F3ED', ink: '#302E2A', muted: '#77736A', accent: '#BD654D', line: '#E2DDD3', sage: '#60765C' };
export const styles = StyleSheet.create({
  page: { gap: 24, paddingBottom: 40 }, row: { flexDirection: 'row', alignItems: 'center', gap: 12, flexWrap: 'wrap' },
  card: { padding: 24, borderRadius: 22, borderWidth: 1, borderColor: '#FFFFFF', backgroundColor: 'rgba(255,255,255,0.64)', gap: 16, ...Platform.select({ web: { boxShadow: '0 8px 32px rgba(77,57,37,0.045)', backdropFilter: 'blur(20px)' } as object }) },
  title: { fontSize: 32, color: colors.ink, fontWeight: '600', letterSpacing: -1 },
  subtitle: { fontSize: 15, lineHeight: 24, color: colors.muted },
  heading: { fontSize: 19, fontWeight: '600', color: colors.ink },
  label: { fontSize: 12, fontWeight: '600', letterSpacing: 1.4, color: colors.muted },
  input: { backgroundColor: '#FFFFFFB3', borderWidth: 1, borderColor: colors.line, borderRadius: 12, padding: 14, color: colors.ink, fontSize: 15, minHeight: 48 },
  body: { color: colors.ink, fontSize: 15, lineHeight: 25 },
});
export function Card({ children, style }: { children: React.ReactNode; style?: object }) { return <View style={[styles.card, style]}>{children}</View>; }
export function Button({ label, onPress, disabled, secondary }: { label: string; onPress: () => void; disabled?: boolean; secondary?: boolean }) {
  return <Pressable accessibilityRole="button" accessibilityLabel={label} disabled={disabled} onPress={onPress} style={({ pressed }) => ({ paddingHorizontal: 19, paddingVertical: 13, borderRadius: 12, backgroundColor: secondary ? '#ECE7DE' : colors.accent, opacity: disabled ? 0.45 : pressed ? 0.7 : 1 })}><Text style={{ color: secondary ? colors.ink : '#FFF', fontWeight: '600', fontSize: 14 }}>{label}</Text></Pressable>;
}
export function Field({ label, value, onChange, placeholder, multiline, secure }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string; multiline?: boolean; secure?: boolean }) {
  return <View style={{ gap: 8 }}><Text style={styles.label}>{label}</Text><TextInput accessibilityLabel={label} value={value} onChangeText={onChange} placeholder={placeholder} placeholderTextColor="#999287" secureTextEntry={secure} autoCapitalize="none" multiline={multiline} style={[styles.input, multiline && { minHeight: 110, textAlignVertical: 'top' }]} /></View>;
}
export function Choices({ values, selected, onChange }: { values: string[]; selected: string; onChange: (v: string) => void }) { return <View style={styles.row}>{values.map(v => <Pressable key={v} accessibilityRole="button" accessibilityState={{ selected: selected === v }} onPress={() => onChange(v)} style={{ padding: 10, paddingHorizontal: 16, borderRadius: 10, backgroundColor: selected === v ? '#EEDDD4' : '#F0EDE6', borderWidth: 1, borderColor: selected === v ? '#D8B4A2' : 'transparent' }}><Text style={{ color: selected === v ? '#984F3B' : colors.muted }}>{v.replace('_', ' ')}</Text></Pressable>)}</View>; }
export function Notice({ text, error }: { text: string; error?: boolean }) { return text ? <View accessibilityRole="alert" style={{ padding: 14, backgroundColor: error ? '#F9E5DE' : '#E9EEE4', borderRadius: 12 }}><Text style={{ color: error ? '#9B3F2E' : colors.sage, lineHeight: 22 }}>{text}</Text></View> : null; }
export function Busy({ text = 'Working with your learning material…' }: { text?: string }) { return <View style={styles.row}><ActivityIndicator color={colors.accent} /><Text style={styles.subtitle}>{text}</Text></View>; }
export function PageHeading({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) { return <View style={{ gap: 10 }}><Text style={styles.label}>{eyebrow}</Text><Text style={styles.title}>{title}</Text><Text style={styles.subtitle}>{description}</Text></View>; }

