import React, { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { studioRequest, StudioJob, getCloudHistory } from "../studioClient";
import type { GenerationHistoryItem } from "../historyStorage";
import { useAppTheme } from "../theme";
import Icon from "./Icon";
export default function JobsPanel({ onResume }: { onResume: (item: GenerationHistoryItem) => void }) {
  const { colors } = useAppTheme();
  const [jobs, setJobs] = useState<StudioJob[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const mounted = useRef(false);
  const fetching = useRef(false);
  const refresh = useCallback(async () => {
    if (fetching.current) return;
    fetching.current = true;
    try {
      const items = await studioRequest<StudioJob[]>("/studio/jobs");
      if (mounted.current) { setJobs(items); setError(null); }
    } catch (failure) {
      if (mounted.current) setError(failure instanceof Error ? failure.message : "Unable to load activity.");
    } finally { fetching.current = false; if (mounted.current) setLoading(false); }
  }, []);
  useEffect(() => {
    mounted.current = true; void refresh();
    const timer = setInterval(() => { if (typeof document === "undefined" || !document.hidden) void refresh(); }, 15000);
    const onOnline = () => void refresh();
    if (typeof window !== "undefined") window.addEventListener("online", onOnline);
    return () => { mounted.current = false; clearInterval(timer); if (typeof window !== "undefined") window.removeEventListener("online", onOnline); };
  }, [refresh]);
  const open = async (job: StudioJob) => {
    const id = job.result?.history_id || job.generation_id; if (!id) return;
    setBusy(true);
    try { onResume(await getCloudHistory(id)); } catch (failure) { setError(failure instanceof Error ? failure.message : "Unable to retrieve result."); }
    finally { setBusy(false); }
  };
  const retry = async (job: StudioJob) => {
    setBusy(true);
    try { await studioRequest("/studio/jobs/" + job.id + "/retry", { method: "POST" }); await refresh(); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "Unable to retry."); }
    finally { setBusy(false); }
  };
  const running = jobs.filter(job => job.status === "queued" || job.status === "running").length;
  const status = loading ? "Checking..." : error ? "Connection unavailable" : running ? running + " in progress" : jobs.length ? jobs.length + " recent" : "No recent activity";
  return <View style={{ gap: 10, padding: 14, borderWidth: 1, borderColor: colors.border, borderRadius: 18, backgroundColor: colors.surfaceSoft }}>
    <Pressable accessibilityRole="button" accessibilityLabel="Toggle background activity" accessibilityState={{ expanded }} onPress={() => setExpanded(!expanded)}
      style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12, minHeight: 32 }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 9 }}><Icon name="activity" color={colors.primaryBright} /><Text style={{ color: colors.text, fontWeight: "700", fontSize: 13 }}>Activity</Text></View>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
        {loading && <ActivityIndicator size="small" color={colors.primaryBright} />}
        <Text style={{ color: error ? colors.danger : colors.textMuted, fontSize: 12 }}>{status}</Text><Icon name={expanded ? "minus" : "plus"} size={15} color={colors.textMuted} />
      </View>
    </Pressable>
    {error && <View style={{ gap: 8 }}><Text accessibilityRole="alert" style={{ color: colors.danger, fontSize: 13 }}>{error}</Text><Pressable accessibilityRole="button" accessibilityLabel="Retry cloud connection" onPress={() => void refresh()} style={{ alignSelf: "flex-start", minHeight: 36, justifyContent: "center" }}><Text style={{ color: colors.primaryBright, fontWeight: "600" }}>Retry connection</Text></Pressable></View>}
    {expanded && <>
      <Text style={{ color: colors.textMuted, fontSize: 12, lineHeight: 18 }}>Creations continue in the background. Open completed results here or from History.</Text>
      {!loading && !error && !jobs.length && <Text style={{ color: colors.textDim, fontSize: 12 }}>Your next creation will appear here.</Text>}
      {jobs.slice(0, 10).map(job => <View key={job.id} style={{ gap: 5, paddingVertical: 10, borderTopWidth: 1, borderTopColor: colors.border }}>
        <Text style={{ color: colors.text, fontSize: 13 }}>{job.kind} · {job.stage}</Text>
        {job.error && <Text style={{ color: colors.danger }}>{job.error}</Text>}
        {job.status === "completed" && !job.result?.history_id && !job.generation_id && <Text style={{ color: colors.textMuted }}>Enhanced prompt saved in History.</Text>}
        {job.status === "completed" && (job.result?.history_id || job.generation_id) && <Pressable accessibilityRole="button" disabled={busy} onPress={() => void open(job)} style={{ minHeight: 36, justifyContent: "center" }}><Text style={{ color: colors.primaryBright }}>Open result</Text></Pressable>}
        {job.status === "failed" && <Pressable accessibilityRole="button" disabled={busy} onPress={() => void retry(job)} style={{ minHeight: 36, justifyContent: "center" }}><Text style={{ color: colors.primaryBright }}>Retry job</Text></Pressable>}
      </View>)}
    </>}
  </View>;
}
