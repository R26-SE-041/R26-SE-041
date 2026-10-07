import React, { useState } from 'react';
import { Text, View } from 'react-native';
import { api } from '../api';
import { services } from '../config';
import { Button, Card, colors, PageHeading, styles } from '../ui';

export default function Connections() {
  const [status, setStatus] = useState<Record<string, string>>({}), [busy, setBusy] = useState(false);
  const check = async () => { setBusy(true); await Promise.all(Object.entries(services).map(async ([id, service]) => { try { await api(id as keyof typeof services, service.health, undefined, { timeout: 10000 }); setStatus(v => ({ ...v, [id]: 'Reachable' })); } catch (e) { setStatus(v => ({ ...v, [id]: e instanceof Error ? e.message : 'Unavailable' })); } })); setBusy(false); };
  return <View style={styles.page}><PageHeading eyebrow="YOUR WORKSPACE" title="Connections & account" description="One learning workspace, powered by your four research services." /><Card><Text style={styles.heading}>Backend connections</Text>{Object.entries(services).map(([id, service]) => <View key={id} style={{ gap: 5, borderBottomWidth: 1, borderColor: colors.line, paddingBottom: 14 }}><Text style={styles.body}>{service.label}</Text><Text selectable style={styles.subtitle}>{service.url}</Text>{status[id] && <Text style={styles.subtitle}>{status[id]}</Text>}</View>)}<Button label={busy ? 'Checking…' : 'Check connections'} disabled={busy} onPress={check} /></Card><Card><Text style={styles.heading}>Your shared account</Text><Text style={styles.body}>Use the common Supabase Auth project for a consistent learner identity. Your common app session is stored separately from the original frontends.</Text><Text style={styles.subtitle}>Setup instructions and backend compatibility details are in common-frontend/README.md.</Text></Card></View>;
}
