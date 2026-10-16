export const PROCESS_LABELS = {
  prompt: "Prompt enhancement",
  image: "Image generation",
  eval: "Quality evaluation",
  labels: "Automatic labeling",
  identify: "Object identification",
  explain: "Region explanation",
  ask: "Question answering",
  threed: "3D generation",
};

export type ProcessKey = keyof typeof PROCESS_LABELS;
export type ProcessOutcome = "completed" | "failed";

export function formatDuration(milliseconds: number): string {
  const duration = Math.max(0, milliseconds);
  if (duration < 1_000) return `${Math.round(duration)} ms`;
  if (duration < 60_000) return `${(duration / 1_000).toFixed(1)} s`;
  const totalSeconds = Math.round(duration / 1_000);
  return `${Math.floor(totalSeconds / 60)} min ${totalSeconds % 60} s`;
}

export function jobElapsed(job: { created_at: string; updated_at?: string; status: string }, now: number): number | null {
  const started = Date.parse(job.created_at);
  const finished = job.status === "completed" || job.status === "failed" ? Date.parse(job.updated_at || "") : now;
  return Number.isFinite(started) && Number.isFinite(finished) ? Math.max(0, finished - started) : null;
}
