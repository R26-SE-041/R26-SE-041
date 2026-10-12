import React from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, useWindowDimensions, View } from 'react-native';
import { colors, fonts, webTransition } from './theme';
export { colors, fonts } from './theme';

export const styles = StyleSheet.create({
  page: { gap: 24, paddingBottom: 40 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, flexWrap: 'wrap' },
  card: { padding: 24, borderRadius: 12, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface, gap: 16 },
  title: { fontFamily: fonts.heading, fontSize: 38, lineHeight: 46, color: colors.ink, fontWeight: '400', letterSpacing: -1.2 },
  subtitle: { fontFamily: fonts.body, fontSize: 14, lineHeight: 23, color: colors.muted },
  heading: { fontFamily: fonts.heading, fontSize: 23, lineHeight: 30, fontWeight: '400', color: colors.ink },
  label: { fontFamily: fonts.body, fontSize: 11, lineHeight: 17, fontWeight: '600', letterSpacing: 1.1, color: colors.muted },
  input: { fontFamily: fonts.body, backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.line, borderRadius: 8, padding: 14, color: colors.ink, fontSize: 15, lineHeight: 23, minHeight: 48, ...webTransition },
  body: { fontFamily: fonts.body, color: colors.ink, fontSize: 15, lineHeight: 25 },
  divider: { height: 1, backgroundColor: colors.line },
});
export function Card({ children, style }: { children: React.ReactNode; style?: object }) {
  return <View style={[styles.card, style]}>{children}</View>;
}
export function Button({ label, onPress, disabled, secondary }: { label: string; onPress: () => void; disabled?: boolean; secondary?: boolean }) {
  return <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled: !!disabled }} disabled={disabled} onPress={onPress} style={state => ({
    minHeight: 44, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 18, paddingVertical: 11, borderRadius: 8,
    borderWidth: 1, borderColor: secondary ? colors.line : 'transparent',
    backgroundColor: secondary ? ('hovered' in state && state.hovered ? colors.soft : colors.surface) : ('hovered' in state && state.hovered ? colors.accentHover : colors.accent),
    opacity: disabled ? 0.4 : state.pressed ? 0.75 : 1, ...webTransition,
  })}><Text style={{ fontFamily: fonts.body, color: secondary ? colors.ink : '#FFF', fontWeight: '600', fontSize: 13 }}>{label}</Text></Pressable>;
}
export function Field({ label, value, onChange, placeholder, multiline, secure }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string; multiline?: boolean; secure?: boolean }) {
  return <View style={{ gap: 8 }}><Text style={styles.label}>{label}</Text><TextInput accessibilityLabel={label} value={value} onChangeText={onChange} placeholder={placeholder} placeholderTextColor={colors.muted} secureTextEntry={secure} autoCapitalize="none" multiline={multiline} style={[styles.input, multiline && { minHeight: 120, textAlignVertical: 'top' }]} /></View>;
}
export function Choices({ values, selected, onChange }: { values: string[]; selected: string; onChange: (v: string) => void }) {
  return <View style={[styles.row, { gap: 6 }]}>{values.map(v => <Pressable key={v} accessibilityRole="button" accessibilityState={{ selected: selected === v }} onPress={() => onChange(v)} style={state => ({
    paddingVertical: 10, paddingHorizontal: 15, minHeight: 42, borderRadius: 8,
    backgroundColor: selected === v ? colors.accentSoft : ('hovered' in state && state.hovered ? colors.soft : colors.surface),
    borderWidth: 1, borderColor: selected === v ? '#DCB6A5' : colors.line, ...webTransition,
  })}><Text style={{ fontFamily: fonts.body, fontSize: 13, fontWeight: selected === v ? '600' : '400', color: selected === v ? colors.accentHover : colors.muted }}>{v.replace(/_/g, ' ')}</Text></Pressable>)}</View>;
}
export function Notice({ text, error }: { text: string; error?: boolean }) {
  return text ? <View accessibilityRole="alert" style={{ padding: 14, backgroundColor: error ? colors.dangerSoft : colors.successSoft, borderRadius: 8 }}><Text style={{ fontFamily: fonts.body, fontSize: 13, color: error ? colors.danger : colors.sage, lineHeight: 22 }}>{text}</Text></View> : null;
}
export function Busy({ text = 'Working with your learning material…' }: { text?: string }) {
  return <View accessibilityLiveRegion="polite" style={styles.row}><ActivityIndicator color={colors.accent} /><Text style={styles.subtitle}>{text}</Text></View>;
}
export function PageHeading({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  const { width } = useWindowDimensions();
  return <View style={{ gap: 10, paddingVertical: 8 }}><Text style={styles.label}>{eyebrow}</Text><Text accessibilityRole="header" style={[styles.title, width < 600 && { fontSize: 30, lineHeight: 38 }]}>{title}</Text><Text style={[styles.subtitle, { maxWidth: 680 }]}>{description}</Text></View>;
}
export function FormGrid({ children }: { children: React.ReactNode }) {
  const { width } = useWindowDimensions();
  return <View style={{ flexDirection: width > 1000 ? 'row' : 'column', gap: 24 }}>{React.Children.map(children, child => <View style={{ flex: 1, minWidth: 0, gap: 16 }}>{child}</View>)}</View>;
}
