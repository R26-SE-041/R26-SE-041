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
