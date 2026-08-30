import React, { createContext, useContext, useMemo, useState } from "react";
import { Platform, StyleSheet } from "react-native";

export type ThemeMode = "dark" | "light";

export const darkColors = {
  background: "#201914",
  surface: "rgba(53, 41, 32, 0.78)",
  surfaceSoft: "rgba(255, 244, 226, 0.08)",
  border: "rgba(255, 232, 202, 0.18)",
  primary: "#d97745",
  primaryBright: "#f2a06f",
  cyan: "#d8a56d",
  text: "#fff7ea",
  textMuted: "#d9c7b2",
  textDim: "#a99580",
  success: "#91a878",
  warning: "#e9ad5c",
  danger: "#e27661",
  canvas: "#17120f",
  shadow: "rgba(8,4,2,0.36)",
} as const;

export const lightColors: ColorPalette = {
  background: "#f4eadb",
  surface: "rgba(255, 255, 255, 0.48)",
  surfaceSoft: "rgba(255, 253, 247, 0.36)",
  border: "rgba(255, 255, 255, 0.68)",
  primary: "#c95f32",
  primaryBright: "#b94f27",
  cyan: "#a5683f",
  text: "#33261f",
  textMuted: "#705d50",
  textDim: "#927b6c",
  success: "#647a51",
  warning: "#c88935",
  danger: "#b84c3d",
  canvas: "#e8dac6",
  shadow: "rgba(91,54,29,0.14)",
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
    borderRadius: 24,
    padding: 22,
    ...Platform.select({
      web: { boxShadow: `0 24px 70px ${colors.shadow}, inset 0 1px 0 rgba(255,255,255,0.82)`, backdropFilter: "blur(24px) saturate(125%)", WebkitBackdropFilter: "blur(24px) saturate(125%)" } as object,
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
    gap: 8,
  },
  primaryButton: { backgroundColor: colors.primary },
  secondaryButton: {
    backgroundColor: colors.surfaceSoft,
    borderColor: colors.border,
    borderWidth: 1,
  },
  buttonText: { color: "#ffffff", fontWeight: "700", fontSize: 14 },
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
