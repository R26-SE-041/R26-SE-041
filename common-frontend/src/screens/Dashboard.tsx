import React from 'react';
import { Pressable, Text, useWindowDimensions, View } from 'react-native';
import { modules, type Page } from '../navigation';
import Icon from '../features/visual/components/Icon';
import { fonts, webTransition } from '../theme';
import { colors, styles } from '../ui';

export default function Dashboard({ name, open }: { name: string; open: (page: Page) => void }) {
  const { width } = useWindowDimensions();
  return <View style={styles.page}>
    <View style={styles.row}><Text style={styles.label}>A SPACE TO THINK, EXPLORE & LEARN</Text><View style={{ flex: 1 }} /><Text style={[styles.subtitle, { fontSize: 12 }]}>G.C.E. A/L Biology</Text></View>
    <View style={{ gap: 16, paddingTop: 24, paddingBottom: 32 }}>
      <Text accessibilityRole="header" style={[styles.title, { fontSize: width > 700 ? 54 : 36, lineHeight: width > 700 ? 62 : 44 }]}>A little curiosity.{'\n'}A deeper understanding.</Text>
      <Text style={[styles.subtitle, { maxWidth: 560, fontSize: 15, lineHeight: 25 }]}>Welcome{name ? `, ${name}` : ''}. Make sense of a concept, find your next question, or see your study material in a new light.</Text>
    </View>
    <View style={[styles.row, { paddingTop: 14 }]}><Text style={styles.heading}>Four ways to understand.</Text><View style={{ flex: 1 }} /><Text style={[styles.subtitle, { fontSize: 12 }]}>Your learning toolkit</Text></View>
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 16 }}>{modules.map((module, index) => <Pressable key={module.id} accessibilityRole="button" accessibilityLabel={`Open ${module.label}`} onPress={() => open(module.id)} style={state => ({ flexBasis: width >= 1000 ? '47%' : '100%', flexGrow: 1, minWidth: 0, borderWidth: 1, borderColor: 'hovered' in state && state.hovered ? '#C8C4B8' : colors.line, backgroundColor: 'hovered' in state && state.hovered ? '#FDFCFA' : colors.surface, borderRadius: 12, opacity: state.pressed ? 0.8 : 1, ...webTransition })}>
      <View style={{ padding: 26, gap: 16, height: '100%' }}>
        <View style={styles.row}><View style={{ backgroundColor: module.tint, width: 42, height: 42, borderRadius: 9, alignItems: 'center', justifyContent: 'center' }}><Icon name={module.icon} size={22} color={colors.ink} /></View><View style={{ flex: 1 }} /><Text style={styles.label}>0{index + 1}</Text></View>
        <View style={{ gap: 7 }}><Text style={[styles.heading, { fontSize: 27, lineHeight: 34 }]}>{module.label}</Text><Text style={styles.subtitle}>{module.description}</Text></View>
        <View style={styles.divider} /><Text style={[styles.subtitle, { fontSize: 12 }]}>{module.tag}</Text>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 7 }}>{module.capabilities.map(label => <Text key={label} style={{ fontFamily: fonts.body, fontSize: 11, color: colors.muted, backgroundColor: colors.bg, borderRadius: 5, paddingHorizontal: 8, paddingVertical: 5 }}>{label}</Text>)}</View>
        <Text style={{ fontFamily: fonts.body, color: colors.accentHover, fontSize: 13, marginTop: 'auto', paddingTop: 4 }}>Open workspace ↗</Text>
      </View>
    </Pressable>)}</View>
    <Text style={[styles.subtitle, { textAlign: 'center', fontSize: 11, paddingTop: 16 }]}>Thoughtful tools. Your own pace. · LearnX</Text>
  </View>;
}
