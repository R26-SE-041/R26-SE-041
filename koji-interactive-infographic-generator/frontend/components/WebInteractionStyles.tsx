import React from "react";
import { Platform } from "react-native";
import type { ColorPalette, ThemeMode } from "../theme";

/** Shared mouse feedback and accessible keyboard focus for the web workspace. */
export default function WebInteractionStyles({ colors, mode }: { colors: ColorPalette; mode: ThemeMode }) {
  if (Platform.OS !== "web") return null;
  const controls = ':is(button, [role="button"], [role="tab"], [tabindex="0"]):not(input):not(textarea):not([aria-label="Dismiss account menu"])';
  return React.createElement("style", null, `
    ${controls} { transition: filter 140ms ease, box-shadow 140ms ease, background-color 140ms ease; -webkit-tap-highlight-color: transparent; }
    ${controls}:focus:not(:focus-visible) { outline: none !important; }
    ${controls}:focus-visible { outline: 2px solid ${colors.primaryBright} !important; outline-offset: 3px; }
    svg:focus { outline: none; }
    @media (hover: hover) and (pointer: fine) {
      ${controls}:not(:disabled):not([aria-disabled="true"]):hover { cursor: pointer; filter: brightness(${mode === "dark" ? "1.16" : ".95"}); box-shadow: inset 0 0 0 1px ${colors.primaryBright}; }
    }
    @media (prefers-reduced-motion: reduce) { ${controls} { transition: none; } }
  `);
}
