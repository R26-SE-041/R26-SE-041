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
import WebTheme from './src/WebTheme';
import Icon, { type IconName } from './src/features/visual/components/Icon';
import { fonts, webData, webTransition } from './src/theme';
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
  if (!session && !preview) return <View {...webData({ workspace: 'true' })} style={{ flex: 1, backgroundColor: colors.bg }}><WebTheme /><Login explore={() => setPreview(true)} /></View>;
  const nav: { id: Page; label: string; icon: IconName }[] = [
    { id: 'home', label: 'Overview', icon: 'layers' },
    ...modules,
    { id: 'settings', label: 'Connections', icon: 'activity' },
  ];
  const wide = width > 850;
  return <View {...webData({ workspace: 'true' })} style={{ flex: 1, backgroundColor: colors.bg, flexDirection: wide ? 'row' : 'column' }}>
    <WebTheme />
    {wide && <View style={{ width: 232, borderRightWidth: 1, borderColor: colors.line, padding: 20, backgroundColor: colors.sidebar, gap: 30 }}>
      <View style={styles.row}><Icon name="sun" size={27} color={colors.accent} /><Text style={{ fontFamily: fonts.heading, fontSize: 25, color: colors.ink }}>LearnX</Text></View>
      <View style={{ gap: 14 }}><Text style={[styles.label, { paddingHorizontal: 12 }]}>YOUR WORKSPACE</Text>
        <View style={{ gap: 4 }}>{nav.map(item => <Pressable key={item.id} accessibilityRole="button" accessibilityState={{ selected: page === item.id }} onPress={() => open(item.id)} style={state => ({ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, minHeight: 44, borderRadius: 8, backgroundColor: page === item.id ? colors.soft : ('hovered' in state && state.hovered ? '#ECEAE2' : 'transparent'), ...webTransition })}>
          <Icon name={item.icon} size={18} color={page === item.id ? colors.accent : colors.muted} /><Text style={{ fontFamily: fonts.body, color: page === item.id ? colors.ink : colors.muted, fontWeight: page === item.id ? '600' : '400', fontSize: 13 }}>{item.label}</Text>
        </Pressable>)}</View>
      </View>
      <View style={{ flex: 1 }} />
      <View style={{ gap: 12, borderTopWidth: 1, borderColor: colors.line, paddingTop: 20 }}><Text style={styles.subtitle}>A little curiosity.{'\n'}A deeper understanding.</Text><Text style={[styles.label, { fontSize: 9 }]}>LEARNX · R26-SE-041</Text></View>
    </View>}
    <View style={{ flex: 1, minWidth: 0 }}>
      <View style={{ paddingHorizontal: wide ? 36 : 18, paddingVertical: 14, minHeight: 72, borderBottomWidth: 1, borderColor: colors.line, flexDirection: 'row', alignItems: 'center', gap: 12 }}>
        <Text style={[styles.subtitle, { fontSize: 12 }]}>{wide ? 'Workspace  /  ' + nav.find(v => v.id === page)?.label : 'LearnX'}</Text><View style={{ flex: 1 }} />
        <Text numberOfLines={1} style={[styles.subtitle, { fontSize: 12, maxWidth: wide ? 260 : 110 }]}>{preview && !session ? 'Preview workspace' : session?.user.email}</Text>
        <Button label={session ? 'Sign out' : 'Sign in'} secondary onPress={async () => { if (auth && session) { const { error } = await auth.auth.signOut({ scope: 'local' }); if (error) { setNotice(error.message); return; } } setPreview(false); setPage('home'); setNotice(''); }} />
      </View>
      {!wide && <View><ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ padding: 12, gap: 8 }}>{nav.map(v => <Button key={v.id} label={v.label} secondary={page !== v.id} onPress={() => open(v.id)} />)}</ScrollView></View>}
    <ScrollView key={session?.user.id || 'preview'} contentContainerStyle={{ padding: wide ? 36 : 18, maxWidth: 1200, width: '100%', alignSelf: 'center', gap: 20 }}><Notice text={notice} />{preview && !session && <Notice text="Preview mode: explore all four workspaces. Sign in to generate, upload to a backend, or use saved account data." />}{page === 'home' && <View {...webData({ pageEnter: 'home' })}><Dashboard name={typeof session?.user.user_metadata.full_name === 'string' ? session.user.user_metadata.full_name.split(' ')[0] : ''} open={open} /></View>}{page === 'settings' && <Connections />}{visited.owner === workspaceOwner && <>
      {visited.pages.includes('visual') && <View {...webData({ pageEnter: page === 'visual' ? 'visual' : undefined })} style={{ display: page === 'visual' ? 'flex' : 'none' }}><FeatureBoundary name="Visual studio"><VisualStudio accessToken={session?.access_token} userId={workspaceOwner} /></FeatureBoundary></View>}
      {visited.pages.includes('quiz') && <View {...webData({ pageEnter: page === 'quiz' ? 'quiz' : undefined })} style={{ display: page === 'quiz' ? 'flex' : 'none' }}><FeatureBoundary name="Adaptive practice"><Quiz userId={workspaceOwner} /></FeatureBoundary></View>}
      {visited.pages.includes('notes') && <View {...webData({ pageEnter: page === 'notes' ? 'notes' : undefined })} style={{ display: page === 'notes' ? 'flex' : 'none' }}><FeatureBoundary name="Image to notes"><Notes userId={workspaceOwner} /></FeatureBoundary></View>}
      {visited.pages.includes('audio') && <View {...webData({ pageEnter: page === 'audio' ? 'audio' : undefined })} style={{ display: page === 'audio' ? 'flex' : 'none' }}><FeatureBoundary name="Audio tutor"><AudioTutor userId={workspaceOwner} preview={!session} /></FeatureBoundary></View>}
    </>}</ScrollView></View></View>;
}
