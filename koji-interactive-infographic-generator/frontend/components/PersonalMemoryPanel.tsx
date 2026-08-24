import React, { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import Icon from "./Icon";
import { ColorPalette, makeSharedStyles, useAppTheme } from "../theme";

interface Preference {
  id: string;
  agent_name: string;
  content: string;
  confidence: number;
  evidence_count: number;
  status: string;
}

interface Props { accessToken?: string; apiUrl: string }

export default function PersonalMemoryPanel({ accessToken, apiUrl }: Props) {
  const { colors } = useAppTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const shared = useMemo(() => makeSharedStyles(colors), [colors]);
  const [enabled, setEnabled] = useState(false);
  const [preferences, setPreferences] = useState<Preference[]>([]);
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);

  const headers = useMemo(() => ({
    "Content-Type": "application/json",
    Authorization: `Bearer ${accessToken}`,
  }), [accessToken]);

  const load = async () => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    try {
      const [settingsResponse, preferencesResponse] = await Promise.all([
        fetch(`${apiUrl}/memory/settings`, { headers }),
        fetch(`${apiUrl}/memory/preferences`, { headers }),
      ]);
      if (!settingsResponse.ok || !preferencesResponse.ok) throw new Error("Personal memory could not be loaded");
      const settings = await settingsResponse.json();
      const preferenceData = await preferencesResponse.json();
      setEnabled(Boolean(settings.memory_enabled));
      setPreferences(Array.isArray(preferenceData.preferences) ? preferenceData.preferences : []);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Personal memory could not be loaded");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, [accessToken]);
  if (!accessToken) return null;

  const updateEnabled = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiUrl}/memory/settings`, {
        method: "POST", headers, body: JSON.stringify({ memory_enabled: !enabled }),
      });
      if (!response.ok) throw new Error("Memory setting could not be updated");
      const data = await response.json();
      setEnabled(Boolean(data.memory_enabled));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Memory setting could not be updated");
    } finally {
      setLoading(false);
    }
  };

  const revoke = async (id: string) => {
    const response = await fetch(`${apiUrl}/memory/preferences/${encodeURIComponent(id)}/revoke`, { method: "POST", headers });
    if (response.ok) setPreferences((current) => current.map((item) => item.id === id ? { ...item, status: "revoked" } : item));
    else setError("Preference could not be revoked");
  };

  const clear = async () => {
    if (!confirmClear) { setConfirmClear(true); return; }
    setLoading(true);
    const response = await fetch(`${apiUrl}/memory/clear`, { method: "POST", headers });
    if (response.ok) { setPreferences([]); setConfirmClear(false); }
    else setError("Personal memory could not be cleared");
    setLoading(false);
  };

  return (
    <View style={[shared.card, styles.container]}>
      <View style={styles.header}>
        <View style={styles.titleRow}><Icon color={colors.primaryBright} name="layers" size={18} /><Text style={styles.title}>Personal memory</Text></View>
        <Pressable disabled={loading} onPress={updateEnabled} style={[styles.toggle, enabled && styles.toggleEnabled]}>
          {loading && <ActivityIndicator color={colors.text} size="small" />}
          <Text style={styles.toggleText}>{enabled ? "Enabled" : "Disabled"}</Text>
        </Pressable>
      </View>
      <Text style={styles.description}>Opt-in memory activates a preference only after three accepted corrections. It never overrides safety rules.</Text>
      {error && <Text style={styles.error}>{error}</Text>}
      <Pressable onPress={() => setExpanded((value) => !value)} style={styles.linkButton}>
        <Text style={styles.linkText}>{expanded ? "Hide remembered preferences" : `Review remembered preferences (${preferences.length})`}</Text>
      </Pressable>
      {expanded && (
        <View style={styles.list}>
          {preferences.length === 0 && <Text style={styles.empty}>No personal preferences have been learned.</Text>}
          {preferences.map((preference) => (
            <View key={preference.id} style={styles.preference}>
              <View style={styles.preferenceContent}>
                <Text style={styles.agent}>{preference.agent_name.replace("-agent", "")}</Text>
                <Text style={[styles.preferenceText, preference.status === "revoked" && styles.revoked]}>{preference.content}</Text>
                <Text style={styles.meta}>{preference.status} · {preference.evidence_count} evidences · {Math.round(preference.confidence * 100)}% confidence</Text>
              </View>
              {preference.status !== "revoked" && <Pressable onPress={() => void revoke(preference.id)} style={styles.revoke}><Text style={styles.revokeText}>Forget</Text></Pressable>}
            </View>
          ))}
          {preferences.length > 0 && (
            <Pressable onPress={() => void clear()} style={styles.clear}>
              <Text style={styles.clearText}>{confirmClear ? "Press again to permanently clear" : "Clear all personal memory"}</Text>
            </Pressable>
          )}
        </View>
      )}
    </View>
  );
}

const makeStyles = (colors: ColorPalette) => StyleSheet.create({
  container: { gap: 12 },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 },
  titleRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  title: { color: colors.text, fontWeight: "900", fontSize: 15 },
  toggle: { flexDirection: "row", alignItems: "center", gap: 6, borderWidth: 1, borderColor: colors.border, borderRadius: 20, paddingHorizontal: 12, paddingVertical: 8 },
  toggleEnabled: { borderColor: colors.success },
  toggleText: { color: colors.text, fontSize: 12, fontWeight: "800" },
  description: { color: colors.textDim, fontSize: 12, lineHeight: 18 },
  linkButton: { alignSelf: "flex-start", paddingVertical: 4 },
  linkText: { color: colors.primaryBright, fontSize: 12, fontWeight: "800" },
  list: { gap: 9 },
  preference: { flexDirection: "row", gap: 10, alignItems: "center", backgroundColor: colors.surfaceSoft, borderRadius: 12, padding: 12 },
  preferenceContent: { flex: 1, gap: 4 },
  agent: { color: colors.primaryBright, fontSize: 10, fontWeight: "900", textTransform: "uppercase" },
  preferenceText: { color: colors.text, fontSize: 12, lineHeight: 18 },
  revoked: { color: colors.textDim, textDecorationLine: "line-through" },
  meta: { color: colors.textDim, fontSize: 10 },
  revoke: { borderWidth: 1, borderColor: colors.danger, borderRadius: 9, paddingHorizontal: 10, paddingVertical: 7 },
  revokeText: { color: colors.danger, fontSize: 11, fontWeight: "800" },
  clear: { alignSelf: "flex-start", paddingVertical: 8 },
  clearText: { color: colors.danger, fontSize: 11, fontWeight: "800" },
  empty: { color: colors.textDim, fontSize: 12 },
  error: { color: colors.danger, fontSize: 11 },
});
