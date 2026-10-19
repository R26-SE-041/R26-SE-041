import React from "react";
import { Platform } from "react-native";
import type { ColorPalette, ThemeMode } from "../theme";

/** Shared mouse feedback and accessible keyboard focus for the web workspace. */
export default function WebInteractionStyles({ colors, mode }: { colors: ColorPalette; mode: ThemeMode }) {
  if (Platform.OS !== "web") return null;
  const controls = ':is(button, [role="button"], [role="tab"], [tabindex="0"]):not(input):not(textarea):not([aria-label="Dismiss account menu"])';
  return React.createElement("style", null, `
    html, body, #root { background-color: ${colors.background}; font-family: Arial, Helvetica, sans-serif; }
    ::selection { background-color: ${colors.primary}; color: white; }
    input, textarea { caret-color: ${colors.primaryBright}; transition: border-color 200ms ease; }
    input:focus-visible, textarea:focus-visible { outline: 2px solid ${colors.primaryBright}; outline-offset: 2px; }
    ${controls} { transition: border-color 200ms ease, color 200ms ease, background-color 200ms ease, opacity 200ms ease; -webkit-tap-highlight-color: transparent; }
    ${controls}:focus:not(:focus-visible) { outline: none !important; }
    ${controls}:focus-visible { outline: 2px solid ${colors.primaryBright} !important; outline-offset: 3px; }
    [aria-pressed="true"], [role="button"][aria-selected="true"] { box-shadow: inset 0 0 0 1px ${colors.primary}; }
    svg:focus { outline: none; }
    @media (hover: hover) and (pointer: fine) {
      ${controls}:not(:disabled):not([aria-disabled="true"]):hover { cursor: pointer; opacity: .86 !important; }
      [data-theme-button="primary"]:not(:disabled):not([aria-disabled="true"]):hover { background-color: ${colors.buttonHover} !important; opacity: 1; }
      [data-theme-button="secondary"]:not(:disabled):not([aria-disabled="true"]):hover { background-color: ${colors.buttonBackground} !important; opacity: 1; }
      [data-theme-button="secondary"]:not(:disabled):not([aria-disabled="true"]):hover > * { color: ${colors.onButton} !important; }
      [role="tab"]:not([aria-selected="true"]):not([aria-disabled="true"]):hover { background-color: ${colors.surfaceSoft} !important; border-color: ${colors.textDim} !important; opacity: 1; }
    }
    ${controls}:not(:disabled):not([aria-disabled="true"]):active { opacity: .65 !important; }
    @keyframes studio-word-reveal { from { opacity: 0; transform: translateY(24px); } to { opacity: 1; transform: translateY(0); } }
    @media (prefers-reduced-motion: no-preference) {
      [data-reveal-word="true"] { display: inline-block; animation: studio-word-reveal 800ms cubic-bezier(0.16, 1, 0.3, 1) both; }
    }
    @media (prefers-reduced-motion: reduce) {
      ${controls}, input, textarea { transition: none; }
      [data-reveal-word="true"] { animation: none; transform: none; opacity: 1; }
    }
  `);
}
