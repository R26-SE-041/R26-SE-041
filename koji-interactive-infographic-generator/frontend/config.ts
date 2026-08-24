/**
 * Centralized endpoint configuration.
 *
 * Every component MUST import URLs from this file instead of defining its own
 * fallback constants.  This eliminates an entire class of bugs where one
 * component silently uses a stale dev endpoint while the rest use production.
 */

export const PROMPT_AGENT_URL =
  process.env.EXPO_PUBLIC_PROMPT_AGENT_URL ??
  "https://kojithan-y--prompt-agent-api.modal.run";

export const IMAGE_AGENT_URL =
  process.env.EXPO_PUBLIC_IMAGE_AGENT_URL ??
  "https://kojithan-y--image-agent-api.modal.run";

export const INTERACTIVE_AGENT_URL =
  process.env.EXPO_PUBLIC_INTERACTIVE_AGENT_URL ??
  "https://kojithan-y--interactive-agent-api.modal.run";

export const THREED_AGENT_URL =
  process.env.EXPO_PUBLIC_THREED_AGENT_URL ??
  "https://kojithan-y--threed-agent-api.modal.run";

export const BACKEND_URL =
  process.env.EXPO_PUBLIC_BACKEND_HEALTH_URL ??
  "https://kojithan-y--image-gen-orchestrator-api.modal.run";

export const EVAL_AGENT_URL =
  process.env.EXPO_PUBLIC_EVAL_AGENT_URL ??
  "https://kojithan-y--eval-agent-api.modal.run";
