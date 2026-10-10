import React, { useEffect, useState } from 'react';
import { AppState, Platform, Pressable, ScrollView, Text, useWindowDimensions, View } from 'react-native';
import type { Session } from '@supabase/supabase-js';
import { auth } from './src/auth';
import FeatureBoundary from './src/FeatureBoundary';
import PasswordRecovery from './src/PasswordRecovery';
import { AudioTutor, Notes, Quiz, VisualStudio } from './src/modules';
import { modules, type Page } from './src/navigation';
import Connections from './src/screens/Connections';
import Dashboard from './src/screens/Dashboard';
import Login from './src/screens/Login';
import { Button, Busy, colors, Notice, styles } from './src/ui';

export default function App() {
  const [session, setSession] = useState<Session | null>(null), [ready, setReady] = useState(!auth), [preview, setPreview] = useState(false), [page, setPage] = useState<Page>('home'), [notice, setNotice] = useState(''); const { width } = useWindowDimensions();
  const [visited, setVisited] = useState<{ owner: string; pages: Page[] }>({ owner: '', pages: [] });
  const [recovery, setRecovery] = useState(false);
  useEffect(() => {
    if (!auth) return;
    let active = true;
    auth.auth.getSession().then(({ data, error }) => { if (active) { setSession(data.session); setReady(true); if (error) setNotice(error.message); } }).catch(e => { if (active) { setReady(true); setNotice(String(e)); } });
    const { data } = auth.auth.onAuthStateChange((event, current) => { if (active) { setSession(current); setReady(true); if (event === 'PASSWORD_RECOVERY') setRecovery(true); } });
    const sub = Platform.OS !== 'web' ? AppState.addEventListener('change', state => state === 'active' ? auth?.auth.startAutoRefresh() : auth?.auth.stopAutoRefresh()) : null;
    return () => { active = false; data.subscription.unsubscribe(); sub?.remove(); };
  }, []);
  const workspaceOwner = session?.user.id || 'preview';
  const open = (next: Page) => {
    setVisited(current => ({
      owner: workspaceOwner,
      pages: current.owner === workspaceOwner ? [...new Set([...current.pages, next])] : [next],
    }));
    setNotice('');
    setPage(next);
  };
  if (!ready) return <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: colors.bg }}><Busy text="Opening your workspace…" /></View>;
  if (recovery && session) return <PasswordRecovery done={() => setRecovery(false)} />;
  if (!session && !preview) return <View style={{ flex: 1, backgroundColor: colors.bg }}><Login explore={() => setPreview(true)} /></View>;
  const nav = [{ id: 'home', label: 'Overview', icon: '⌂' }, ...modules, { id: 'settings', label: 'Connections', icon: '⚙' }];
  return <View style={{ flex: 1, backgroundColor: colors.bg, flexDirection: width > 850 ? 'row' : 'column' }}>{width > 850 && <View style={{ width: 238, borderRightWidth: 1, borderColor: colors.line, padding: 24, backgroundColor: '#EEE9DF80', gap: 32 }}><Text style={{ fontSize: 24, fontWeight: '600', color: colors.ink }}>✳ BioLearnX</Text><Text style={styles.label}>LEARNING SPACE</Text><View style={{ gap: 8 }}>{nav.map(item => <Pressable key={item.id} accessibilityRole="button" accessibilityState={{ selected: page === item.id }} onPress={() => open(item.id as Page)} style={{ padding: 13, borderRadius: 12, backgroundColor: page === item.id ? '#E5D8CC' : 'transparent' }}><Text style={{ color: page === item.id ? '#914F3D' : colors.muted, fontWeight: page === item.id ? '600' : '400', fontSize: 14 }}>{item.icon}   {item.label}</Text></Pressable>)}</View><View style={{ flex: 1 }} /><Text style={styles.subtitle}>One workspace.{'\n'}Many ways to understand.</Text><Text style={[styles.label, { fontSize: 10 }]}>R26-SE-041 · RESEARCH PROJECT</Text></View>}
    <View style={{ flex: 1 }}><View style={{ paddingHorizontal: width > 850 ? 40 : 20, paddingVertical: 18, borderBottomWidth: 1, borderColor: colors.line, flexDirection: 'row', alignItems: 'center', gap: 12 }}><Text style={{ color: colors.muted, fontSize: 13 }}>{width > 850 ? 'Workspace  /  ' + nav.find(v => v.id === page)?.label : '✳ BioLearnX'}</Text><View style={{ flex: 1 }} /><Text style={{ color: colors.muted, fontSize: 12 }}>{preview && !session ? 'Preview' : session?.user.email}</Text><Button label={session ? 'Sign out' : 'Sign in'} secondary onPress={async () => { if (auth && session) { const { error } = await auth.auth.signOut({ scope: 'local' }); if (error) { setNotice(error.message); return; } } setPreview(false); setPage('home'); setNotice(''); }} /></View>
    {width <= 850 && <View><ScrollView horizontal contentContainerStyle={{ padding: 12, gap: 8 }}>{nav.map(v => <Button key={v.id} label={v.label} secondary={page !== v.id} onPress={() => open(v.id as Page)} />)}</ScrollView></View>}
    <ScrollView key={session?.user.id || 'preview'} contentContainerStyle={{ padding: width > 850 ? 40 : 20, maxWidth: 1160, width: '100%', alignSelf: 'center', gap: 20 }}><Notice text={notice} />{preview && !session && <Notice text="Preview mode: explore all four workspaces. Sign in to generate, upload to a backend, or use saved account data." />}{page === 'home' && <Dashboard name={typeof session?.user.user_metadata.full_name === 'string' ? session.user.user_metadata.full_name.split(' ')[0] : ''} open={open} />}{page === 'settings' && <Connections />}{visited.owner === workspaceOwner && <>
      {visited.pages.includes('visual') && <View style={{ display: page === 'visual' ? 'flex' : 'none' }}><FeatureBoundary name="Visual studio"><VisualStudio accessToken={session?.access_token} userId={workspaceOwner} /></FeatureBoundary></View>}
      {visited.pages.includes('quiz') && <View style={{ display: page === 'quiz' ? 'flex' : 'none' }}><FeatureBoundary name="Adaptive practice"><Quiz userId={workspaceOwner} /></FeatureBoundary></View>}
      {visited.pages.includes('notes') && <View style={{ display: page === 'notes' ? 'flex' : 'none' }}><FeatureBoundary name="Image to notes"><Notes userId={workspaceOwner} /></FeatureBoundary></View>}
      {visited.pages.includes('audio') && <View style={{ display: page === 'audio' ? 'flex' : 'none' }}><FeatureBoundary name="Audio tutor"><AudioTutor userId={workspaceOwner} preview={!session} /></FeatureBoundary></View>}
    </>}</ScrollView></View></View>;
}

