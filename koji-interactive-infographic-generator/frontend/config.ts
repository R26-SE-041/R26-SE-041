/**
 * Centralized endpoint configuration.
 *
 * Every component MUST import URLs from this file instead of defining its own
 * fallback constants.  This eliminates an entire class of bugs where one
 * component silently uses a stale dev endpoint while the rest use production.
 */

export const PROMPT_AGENT_URL =
  process.env.EXPO_PUBLIC_PROMPT_AGENT_URL?.trim() ||
  "https://agal-koji--prompt-agent-api.modal.run";

export const IMAGE_AGENT_URL =
  process.env.EXPO_PUBLIC_IMAGE_AGENT_URL?.trim() ||
  "https://agal-koji--image-agent-api.modal.run";

export const INTERACTIVE_AGENT_URL =
  process.env.EXPO_PUBLIC_INTERACTIVE_AGENT_URL?.trim() ||
  "https://agal-koji--interactive-agent-api.modal.run";

export const THREED_AGENT_URL =
  process.env.EXPO_PUBLIC_THREED_AGENT_URL?.trim() ||
  "https://agal-koji--threed-agent-api.modal.run";

export const BACKEND_URL =
  process.env.EXPO_PUBLIC_BACKEND_HEALTH_URL?.trim() ||
  "https://kojithan-y--image-gen-orchestrator-api.modal.run";

export const EVAL_AGENT_URL =
  process.env.EXPO_PUBLIC_EVAL_AGENT_URL?.trim() ||
  "https://agal-koji--eval-agent-api.modal.run";

const configuredStudioUrl = process.env.EXPO_PUBLIC_STUDIO_API_URL?.trim() ?? "";
// Hosted web builds can reach the CPU API through the site's own origin.
export const STUDIO_API_URL = configuredStudioUrl && typeof window !== "undefined" && process.env.NODE_ENV === "production"
  ? process.env.EXPO_PUBLIC_STUDIO_PROXY_PATH?.trim() || configuredStudioUrl
  : configuredStudioUrl;
export const SUPABASE_URL = process.env.EXPO_PUBLIC_SUPABASE_URL?.trim() ?? "";
export const SUPABASE_ANON_KEY = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY?.trim() ?? "";

export const SKETCH_AGENT_URL = process.env.EXPO_PUBLIC_SKETCH_AGENT_URL?.trim() ||
  "https://agal-koji--sketch-agent-api.modal.run";
