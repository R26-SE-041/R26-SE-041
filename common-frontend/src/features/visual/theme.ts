import React, { createContext, useContext, useMemo, useState } from "react";
import { StyleSheet } from "react-native";
import { colors as sharedColors, fonts, webTransition } from "../../theme";

export type ThemeMode = "dark" | "light";

export const darkColors = {
  background: "#262624", surface: "#30302E", surfaceSoft: "#383835", border: "#484841",
  primary: "#C96442", primaryBright: "#E29B7E", cyan: "#C7A77C", text: "#FAF9F5",
  textMuted: "#C5C2B8", textDim: "#ABA79D", success: "#A6B59A", warning: "#D7B474",
  danger: "#E99586", canvas: "#222220", shadow: "rgba(0,0,0,0.12)",
} as const;
export const lightColors: ColorPalette = {
  background: sharedColors.bg, surface: sharedColors.surface, surfaceSoft: sharedColors.soft,
  border: sharedColors.line, primary: sharedColors.accent, primaryBright: sharedColors.accentHover,
  cyan: "#96754B", text: sharedColors.ink, textMuted: sharedColors.muted, textDim: sharedColors.muted,
  success: sharedColors.sage, warning: "#956A2C", danger: sharedColors.danger,
  canvas: sharedColors.canvas, shadow: "rgba(20,20,19,0.04)",
};

export type ColorPalette = { [Key in keyof typeof darkColors]: string };

interface ThemeContextValue {
  colors: ColorPalette;
  mode: ThemeMode;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue>({
  colors: lightColors,
  mode: "light",
  toggleTheme: () => undefined,
});

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setMode] = useState<ThemeMode>("light");
  const value = useMemo<ThemeContextValue>(() => ({
    colors: mode === "dark" ? darkColors : lightColors,
    mode,
    toggleTheme: () => setMode((current) => current === "dark" ? "light" : "dark"),
  }), [mode]);
  return React.createElement(ThemeContext.Provider, { value }, children);
}

export const useAppTheme = () => useContext(ThemeContext);

export const makeSharedStyles = (colors: ColorPalette) => StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: 12,
    padding: 24,

  },
  label: {
    fontFamily: fonts.body,
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: "600",
    letterSpacing: 1.1,
    textTransform: "uppercase",
  },
  row: { flexDirection: "row", alignItems: "center" },
  wrap: { flexDirection: "row", flexWrap: "wrap", alignItems: "center" },
  button: {
    ...webTransition,
    minHeight: 44,
    paddingHorizontal: 18,
    borderRadius: 8,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: 8,
  },
  primaryButton: { backgroundColor: colors.primary },
  secondaryButton: {
    backgroundColor: colors.surfaceSoft,
    borderColor: colors.border,
    borderWidth: 1,
  },
  buttonText: { fontFamily: fonts.body, color: "#ffffff", fontWeight: "700", fontSize: 14 },
  secondaryButtonText: { fontFamily: fonts.body, color: colors.text, fontWeight: "700", fontSize: 14 },
  disabled: { opacity: 0.45 },
  error: {
    backgroundColor: colors.surface,
    borderColor: colors.danger,
    borderWidth: 1,
    borderRadius: 14,
    padding: 14,
  },
});
