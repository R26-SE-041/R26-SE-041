import { Platform } from "react-native";

// Warm, high-contrast editorial system measured from Anthropic's current site.
export const lightColors = {
  background: "#F1F0E8",
  surface: "#FCFBF8",
  surfaceSoft: "#E5DED0",
  border: "#D2CEC2",
  primary: "#141413",
  primaryBright: "#5E5D59",
  text: "#141413",
  textMuted: "#5E5D59",
  textDim: "#85837C",
  success: "#4D6B50",
  warning: "#96682F",
  danger: "#A44735",
  canvas: "#EEECE5",
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
  display: Platform.OS === "web" ? "Arial, Helvetica, sans-serif" : undefined,
  serif: Platform.OS === "web" ? "Georgia, 'Times New Roman', serif" : "Georgia",
  sans: Platform.OS === "web" ? "Arial, Helvetica, sans-serif" : undefined,
};

export function editorialSurface(colors: AppColors) {
  return {
    borderWidth: 1,
    borderColor: colors.text,
    backgroundColor: colors.surface,
    borderRadius: 26,
    padding: 36,
    marginBottom: 24,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 1,
    shadowRadius: 30,
  };
}

export const glassSurface = editorialSurface;
