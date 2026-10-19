import React, { useEffect } from "react";
import { Platform } from "react-native";
import type { ColorPalette, ThemeMode } from "../theme";
import { motion } from "../designTokens";
import { installDragSelectionGuard } from "../dragSelection";

/** Shared mouse feedback and accessible keyboard focus for the web workspace. */
export default function WebInteractionStyles({ colors, mode }: { colors: ColorPalette; mode: ThemeMode }) {
  useEffect(() => {
    if (Platform.OS === "web" && typeof document !== "undefined") return installDragSelectionGuard(document, window);
  }, []);
  if (Platform.OS !== "web") return null;
  const controls = ':is(button, [role="button"], [role="tab"], [tabindex="0"]):not(input):not(textarea):not([aria-label="Dismiss account menu"])';
  return React.createElement("style", null, `
    html { color-scheme: ${mode}; }
    html, body, #root { background-color: ${colors.background}; font-family: 'Anthropic Sans', Arial, Helvetica, sans-serif; }
    ::selection { background-color: ${colors.accentSoft}; color: ${colors.text}; }
    [data-drag-surface="true"] { touch-action: none; }
    [data-drag-surface="true"], [data-drag-surface="true"] * { user-select: none; -webkit-user-select: none; -webkit-touch-callout: none; }
    [data-drag-surface="true"] input, [data-drag-surface="true"] textarea, [data-drag-surface="true"] [contenteditable="true"] { user-select: text; -webkit-user-select: text; }
    [data-drag-surface="true"] img { -webkit-user-drag: none; }
    html[data-studio-dragging="true"] * { user-select: none !important; -webkit-user-select: none !important; }
    input, textarea { caret-color: ${colors.primaryBright}; transition: border-color 200ms ease; }
    input:focus-visible, textarea:focus-visible { outline: 2px solid ${colors.primaryBright}; outline-offset: 2px; }
    ${controls} { transition: border-color ${motion.duration}ms ease, color ${motion.duration}ms ease, background-color ${motion.duration}ms ease, opacity ${motion.duration}ms ease; -webkit-tap-highlight-color: transparent; }
    ${controls}:focus:not(:focus-visible) { outline: none !important; }
    ${controls}:focus-visible { outline: 2px solid ${colors.primaryBright} !important; outline-offset: 3px; }
    [aria-pressed="true"], [role="button"][aria-selected="true"] { box-shadow: inset 0 0 0 1px ${colors.border}; }
    [data-icon-only="true"] { box-shadow: none !important; }
    #studio-workspaces [role="tab"][aria-selected="true"] { box-shadow: none; }
    textarea::placeholder, input::placeholder { opacity: 1; }
    [data-studio-panel] { overflow-wrap: anywhere; }
    [data-studio-brand] { transition: color ${motion.duration}ms ease; }
    [data-tooltip] { position: relative; overflow: visible; }
    [data-tooltip]::after {
      content: attr(data-tooltip); position: absolute; top: calc(100% + 8px); left: 50%; transform: translateX(-50%);
      padding: 6px 9px; border-radius: 4px; background: ${colors.text}; color: ${colors.background};
      font: 12px/18px Arial, sans-serif; white-space: nowrap; pointer-events: none; z-index: 20; opacity: 0;
    }
    [data-tooltip]:focus-visible::after { opacity: 1; }
    svg:focus { outline: none; }
    @media (hover: hover) and (pointer: fine) {
      [data-studio-brand]:hover { color: ${colors.primary}; }
      [data-tooltip]:hover::after { opacity: 1; }
      ${controls}:not(:disabled):not([aria-disabled="true"]):hover { cursor: pointer; opacity: .86 !important; }
      [data-theme-button="primary"]:not(:disabled):not([aria-disabled="true"]):hover { background-color: ${colors.buttonHover} !important; opacity: 1; }
      [data-theme-button="secondary"]:not(:disabled):not([aria-disabled="true"]):hover { background-color: ${colors.buttonBackground} !important; opacity: 1; }
      [data-theme-button="secondary"]:not(:disabled):not([aria-disabled="true"]):hover > * { color: ${colors.onButton} !important; }
      [role="tab"]:not([aria-selected="true"]):not([aria-disabled="true"]):hover { background-color: ${colors.surfaceSoft} !important; border-color: ${colors.textDim} !important; opacity: 1; }
    }
    ${controls}:not(:disabled):not([aria-disabled="true"]):active { opacity: .65 !important; }
    @keyframes studio-word-reveal { from { opacity: 0; transform: translateY(24px); } to { opacity: 1; transform: translateY(0); } }
    @keyframes studio-panel-reveal { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
    @media (prefers-reduced-motion: no-preference) {
      [data-reveal-word="true"] { display: inline-block; animation: studio-word-reveal ${motion.revealDuration}ms ${motion.easing} both; }
      [data-studio-panel] { animation: studio-panel-reveal ${motion.revealDuration}ms ${motion.easing} both; }
    }
    @media (prefers-reduced-motion: reduce) {
      ${controls}, input, textarea, [data-studio-brand] { transition: none; }
      [data-reveal-word="true"], [data-studio-panel] { animation: none; transform: none; opacity: 1; }
    }
  `);
}
