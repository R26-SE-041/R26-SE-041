import { Platform } from "react-native";

// Palette and typography roles from Anthropic's official October 2026 homepage.
export const lightColors = {
  background: "#F0EEE6",
  surface: "#FAF9F5",
  surfaceSoft: "#E3DACC",
  border: "#D1CFC5",
  primary: "#141413",
  primaryBright: "#5E5D59",
  text: "#141413",
  textMuted: "#5E5D59",
  textDim: "#87867F",
  success: "#4D6B50",
  warning: "#96682F",
  danger: "#A44735",
  canvas: "#E8E6DC",
  shadow: "rgba(20,20,19,0.10)",
} as const;

export const darkColors = lightColors;
export type AppColors = { [K in keyof typeof lightColors]: string };

// Anthropic's marketing site is intentionally light and paper-like. Keeping a
// fixed canvas also prevents the design from changing with the device setting.
export function useAppTheme() {
  return { colors: lightColors as AppColors, isDark: false };
}

export const fonts = {
  display: Platform.OS === "web" ? "'Anthropic Sans', Arial, sans-serif" : undefined,
  serif: Platform.OS === "web" ? "'Anthropic Serif', Georgia, serif" : "Georgia",
  sans: Platform.OS === "web" ? "'Anthropic Sans', Arial, sans-serif" : undefined,
  mono: Platform.OS === "web" ? "'Anthropic Mono', monospace" : "monospace",
};

export function editorialSurface(colors: AppColors) {
  return {
    backgroundColor: colors.surface,
    borderRadius: 24,
    padding: 40,
    marginBottom: 24,
  };
}

export const glassSurface = editorialSurface;
