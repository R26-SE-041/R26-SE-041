import React, { createContext, useContext, useMemo, useState } from "react";
import { Platform, StyleSheet } from "react-native";

export type ThemeMode = "dark" | "light";

export const darkColors = {
  background: "#070711",
  surface: "#141428",
  surfaceSoft: "#22223b",
  border: "#34344d",
  primary: "#8b5cf6",
  primaryBright: "#a78bfa",
  cyan: "#22d3ee",
  text: "#f4f2ff",
  textMuted: "#a7a3c2",
  textDim: "#77728f",
  success: "#34d399",
  warning: "#fbbf24",
  danger: "#fb7185",
  canvas: "#020205",
  shadow: "rgba(0,0,0,0.28)",
} as const;

export const lightColors: ColorPalette = {
  background: "#f4f6fc",
  surface: "#ffffff",
  surfaceSoft: "#eef0f8",
  border: "#d8dbea",
  primary: "#6d28d9",
  primaryBright: "#6d28d9",
  cyan: "#087f9d",
  text: "#19162c",
  textMuted: "#5d5870",
  textDim: "#7f7991",
  success: "#15803d",
  warning: "#b45309",
  danger: "#be123c",
  canvas: "#eef0f8",
  shadow: "rgba(38,32,70,0.12)",
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
  const [mode, setMode] = useState<ThemeMode>("dark");
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
    borderRadius: 20,
    padding: 20,
    ...Platform.select({
      web: { boxShadow: `0 18px 60px ${colors.shadow}` } as object,
      default: { elevation: 5 },
    }),
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
    borderRadius: 13,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
  },
  primaryButton: { backgroundColor: colors.primary },
  secondaryButton: {
    backgroundColor: colors.surfaceSoft,
    borderColor: colors.border,
    borderWidth: 1,
  },
  buttonText: { color: "#fff", fontWeight: "700", fontSize: 14 },
  disabled: { opacity: 0.45 },
  error: {
    backgroundColor: colors.surface,
    borderColor: colors.danger,
    borderWidth: 1,
    borderRadius: 14,
    padding: 14,
  },
});
