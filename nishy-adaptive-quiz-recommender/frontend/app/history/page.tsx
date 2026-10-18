"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import AppHeader from "@/components/ui/AppHeader";
import { useAuth } from "@/components/auth/AuthProvider";
import { getHistory, moveHistory, type HistoryItem } from "@/lib/api";

function title(item: HistoryItem) {
  if (item.title && item.title !== "Document practice") return item.title;
  try { return JSON.parse(item.topics_detected)?.slice(0, 2).join(" · ") || "Document practice"; } catch { return "Document practice"; }
}
function date(value: string) {
  const iso = value.includes("T") ? value : value.replace(" ", "T") + "Z";
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}
export default function History() {
  const { user } = useAuth();
  const [bin, setBin] = useState(false);
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [busy, setBusy] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<HistoryItem | null>(null);
  const [undo, setUndo] = useState<string | null>(null);
  const load = useCallback(async () => {
    setLoading(true); setError("");
    try { setItems(await getHistory(bin)); } catch (err) { setError(err instanceof Error ? err.message : "Unable to load quizzes."); }
    finally { setLoading(false); }
  }, [bin]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (bin || !items.some(x => x.status === "processing")) return;
    const timer = setInterval(() => { getHistory(false).then(setItems).catch(() => {}); }, 12000);
    return () => clearInterval(timer);
  }, [bin, items]);
  async function move(id: string, restore: boolean) {
    setBusy(id); setError("");
    try {
      await moveHistory(id, restore);
      setItems(prev => prev.filter(x => x.session_id !== id));
      setNotice(restore ? "Quiz restored to My quizzes. Your answers and results are safe." : "Quiz moved to the recycle bin.");
      setUndo(restore ? null : id); setConfirm(null); return true;
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to update quiz."); }
    finally { setBusy(null); }
  }
  async function undoMove() {
    if (!undo) return;
    if (await move(undo, true)) await load();
  }
  const shown = useMemo(() => items.filter(x => title(x).toLowerCase().includes(search.toLowerCase()) && (filter === "all" || (filter === "completed" ? x.status === "completed" : x.status !== "completed"))), [items, search, filter]);
  const finished = items.filter(x => x.final_score !== null);
  const average = finished.length ? Math.round(finished.reduce((n,x) => n + (x.final_score ?? 0), 0) / finished.length) : null;
  return <><AppHeader /><main className="history-layout">
    <div className="history-heading"><div><span className="eyebrow">YOUR PERSONAL LEARNING LIBRARY</span><h1>{bin ? "Room for second chances." : "Every attempt counts."}</h1><p className="muted">{bin ? "Restore a quiz whenever you’re ready. Your progress stays with it." : `Welcome${user?.user_metadata?.display_name ? ", " + user.user_metadata.display_name : " back"}. Your practice, progress and next steps, all in one place.`}</p></div><Link href="/upload" className="btn-primary">New quiz <span aria-hidden="true">＋</span></Link></div>
    {!bin && <div className="history-stats"><div><span>QUIZZES SAVED</span><strong>{items.length}</strong></div><div><span>COMPLETED</span><strong>{items.filter(x => x.status === "completed").length}</strong></div><div><span>AVERAGE SCORE</span><strong>{average === null ? "—" : `${average}%`}</strong></div><p>Progress is a practice.<br /><em>Keep showing up.</em></p></div>}
    <div className="history-toolbar"><div className="history-tabs" role="group" aria-label="Quiz library view"><button aria-pressed={!bin} onClick={() => { setBin(false); setFilter("all"); setNotice(""); setUndo(null); }}>My quizzes</button><button aria-pressed={bin} onClick={() => { setBin(true); setFilter("all"); setNotice(""); setUndo(null); }}>Recycle bin</button></div><div className="history-filters"><input aria-label="Search quizzes" placeholder="Search your quizzes…" value={search} onChange={e => setSearch(e.target.value)} /><select aria-label="Filter by progress" value={filter} onChange={e => setFilter(e.target.value)}><option value="all">All progress</option><option value="completed">Completed</option><option value="ongoing">In progress & other</option></select></div></div>
    {notice && <div className="form-alert success" role="status">{notice} {undo && <button onClick={undoMove} disabled={!!busy}>Undo</button>}</div>}
    {error && <div className="form-alert error" role="alert">{error} <button onClick={load}>Try again</button></div>}
    {loading ? <div className="history-empty" role="status">Opening your quiz library…</div> : shown.length ? <div className="history-grid">{shown.map(item => <article className="history-card" key={item.session_id}>
      <div className="history-card-top"><span className={`quiz-status status-${item.status}`}>{bin ? "In recycle bin" : item.status === "ready" ? "Ready to continue" : item.status === "error" ? "Needs attention" : item.status}</span><span>{date(item.created_at)}</span></div>
      <h2>{title(item)}</h2><p className="quiz-meta">{item.num_questions} questions <span>·</span> {item.exam_type.replace("_", " ").toUpperCase()} <span>·</span> {item.difficulty_mode}</p>
      <div className="history-progress"><div style={{ width: `${Math.min(100, (item.answered / item.num_questions) * 100)}%` }} /></div>
      <div className="history-card-score"><span>{item.answered} / {item.num_questions} answered</span>{item.final_score !== null && <strong>{Math.round(item.final_score)}<small>%</small></strong>}</div>
      {bin && item.deleted_at && <p className="field-help">Moved to bin on {date(item.deleted_at)}</p>}
      <div className="history-card-actions">{bin ? <button className="btn-primary" disabled={!!busy} onClick={() => move(item.session_id, true)}>{busy === item.session_id ? "Restoring…" : "↶ Restore quiz"}</button> : <><Link className="history-open" href={`/quiz/${item.session_id}${item.status === "completed" ? "/results" : ""}`}>{item.status === "completed" ? "View results" : item.status === "processing" ? "View progress" : "Continue quiz"} <span aria-hidden="true">↗</span></Link><button className="bin-action" aria-label={`Move ${title(item)} to recycle bin`} disabled={!!busy} onClick={() => setConfirm(item)}>Move to bin</button></>}</div>
    </article>)}</div> : !error && <div className="history-empty"><span aria-hidden="true" className="empty-symbol">{bin ? "↶" : "✧"}</span><h2>{search || filter !== "all" ? "No matching quizzes." : bin ? "A clean slate." : "Your story starts here."}</h2><p>{search || filter !== "all" ? "Try another search or change your filter." : bin ? "Quizzes you move to the recycle bin will appear here, ready to restore." : "Create your first quiz and we’ll keep your progress right here."}</p>{!bin && !search && <Link href="/upload" className="btn-primary">Create a quiz ↗</Link>}</div>}
    <p className="library-footnote">{bin ? "Quizzes stay in your recycle bin until you restore them. Answers, feedback and results are preserved." : "Your library shows your latest 500 quizzes. Only you can access your quizzes and uploaded study materials."}</p>
  </main>{confirm && <div className="confirm-backdrop" onClick={() => !busy && setConfirm(null)}><section className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="bin-title" onClick={e => e.stopPropagation()} onKeyDown={e => { if (e.key === "Escape" && !busy) setConfirm(null); if (e.key === "Tab") { const buttons = e.currentTarget.querySelectorAll<HTMLButtonElement>("button:not(:disabled)"); const first = buttons[0]; const last = buttons[buttons.length - 1]; if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); } else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); } } }}><span className="eyebrow">YOUR PROGRESS IS SAFE</span><h2 id="bin-title">Move this quiz to the bin?</h2><p>“{title(confirm)}” will leave your library. You can restore it with all its answers and results from the recycle bin.</p>{error && <p className="form-alert error" role="alert">{error}</p>}<div><button autoFocus className="nav-link" disabled={!!busy} onClick={() => setConfirm(null)}>Keep quiz</button><button className="btn-primary" disabled={!!busy} onClick={() => move(confirm.session_id, false)}>{busy ? "Moving…" : "Move to recycle bin"}</button></div></section></div>}</>;
}
