import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { Platform, StyleSheet } from "react-native";
import WebInteractionStyles from "./components/WebInteractionStyles";

export type ThemeMode = "dark" | "light";

export const darkColors = {
  background: "#141413",
  surface: "#262624",
  surfaceSoft: "#3d3d3a",
  border: "#faf9f533",
  primary: "#d97757",
  primaryBright: "#faf9f5",
  cyan: "#bcd1ca",
  text: "#faf9f5",
  textMuted: "#d1cfc5",
  textDim: "#b0aea5",
  accentSoft: "#d9775729",
  markerFill: "#d977576b",
  buttonBackground: "#faf9f5",
  buttonHover: "#e8e6dc",
  onButton: "#141413",
  onBrand: "#141413",
  success: "#91a878",
  warning: "#e9ad5c",
  danger: "#e27661",
  canvas: "#191917",
  shadow: "rgba(0,0,0,0.16)",
} as const;

export const lightColors: ColorPalette = {
  background: "#f0eee6",
  surface: "#faf9f5",
  surfaceSoft: "#e8e6dc",
  border: "#1414131a",
  primary: "#c6613f",
  primaryBright: "#141413",
  cyan: "#526344",
  text: "#141413",
  textMuted: "#5e5d59",
  textDim: "#696861",
  accentSoft: "#c6613f1f",
  markerFill: "#c6613f6b",
  buttonBackground: "#141413",
  buttonHover: "#3d3d3a",
  onButton: "#faf9f5",
  onBrand: "#faf9f5",
  success: "#647a51",
  warning: "#c88935",
  danger: "#b84c3d",
  canvas: "#e8e6dc",
  shadow: "rgba(38,38,33,0.06)",
};

export type ColorPalette = { [Key in keyof typeof darkColors]: string };

interface ThemeContextValue {
  colors: ColorPalette;
  mode: ThemeMode;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue>({
  colors: darkColors,
  mode: "dark",
  toggleTheme: () => undefined,
});

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setMode] = useState<ThemeMode>(() => {
    try { return Platform.OS === "web" && window.localStorage.getItem("koji:theme") === "dark" ? "dark" : "light"; }
    catch { return "light"; }
  });
  useEffect(() => {
    if (Platform.OS !== "web") return;
    try { window.localStorage.setItem("koji:theme", mode); } catch { /* Theme still works when storage is unavailable. */ }
  }, [mode]);
  const value = useMemo<ThemeContextValue>(() => ({
    colors: mode === "dark" ? darkColors : lightColors,
    mode,
    toggleTheme: () => setMode((current) => current === "dark" ? "light" : "dark"),
  }), [mode]);
  return React.createElement(ThemeContext.Provider, { value }, React.createElement(WebInteractionStyles, { colors: value.colors, mode }), children);
}

export const useAppTheme = () => useContext(ThemeContext);

export const headingFont = Platform.select({
  web: "Georgia, 'Times New Roman', serif",
  ios: "Georgia",
  default: "serif",
});

// Anthropic's display and UI use custom sans fonts. Use system fallbacks
// rather than bundling fonts whose redistribution rights are unknown.
export const displayFont = Platform.select({ web: "Arial, Helvetica, sans-serif", ios: "System", default: "sans-serif" });
export const bodyFont = Platform.select({ web: "Arial, Helvetica, sans-serif", default: undefined });

export const makeSharedStyles = (colors: ColorPalette) => StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: 8,
    padding: 24,
  },
  label: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 1.1,
    textTransform: "uppercase",
  },
  row: { flexDirection: "row", alignItems: "center" },
  wrap: { flexDirection: "row", flexWrap: "wrap", alignItems: "center" },
  button: {
    minHeight: 46,
    paddingHorizontal: 18,
    borderRadius: 8,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: 8,
  },
  primaryButton: { backgroundColor: colors.buttonBackground },
  secondaryButton: {
    backgroundColor: "transparent",
    borderColor: colors.text,
    borderWidth: 1,
  },
  buttonText: { color: colors.onButton, fontFamily: bodyFont, fontWeight: "500", fontSize: 16 },
  secondaryButtonText: { color: colors.text, fontWeight: "700", fontSize: 14 },
  disabled: { opacity: 0.45 },
  error: {
    backgroundColor: colors.surface,
    borderColor: colors.danger,
    borderWidth: 1,
    borderRadius: 14,
    padding: 14,
  },
});
