import { Platform, useColorScheme } from "react-native";

export const lightColors = {
  background: "#f4eadb",
  surface: "rgba(255, 255, 255, 0.48)",
  surfaceSoft: "rgba(255, 253, 247, 0.36)",
  border: "rgba(255, 255, 255, 0.68)",
  primary: "#c95f32",
  primaryBright: "#b94f27",
  text: "#33261f",
  textMuted: "#705d50",
  textDim: "#927b6c",
  success: "#647a51",
  warning: "#c88935",
  danger: "#b84c3d",
  canvas: "#e8dac6",
  shadow: "rgba(91,54,29,0.14)",
} as const;

export const darkColors = {
  background: "#201914",
  surface: "rgba(53, 41, 32, 0.78)",
  surfaceSoft: "rgba(255, 244, 226, 0.08)",
  border: "rgba(255, 232, 202, 0.18)",
  primary: "#d97745",
  primaryBright: "#f2a06f",
  text: "#fff7ea",
  textMuted: "#d9c7b2",
  textDim: "#a99580",
  success: "#91a878",
  warning: "#e9ad5c",
  danger: "#e27661",
  canvas: "#17120f",
  shadow: "rgba(8,4,2,0.36)",
} as const;

export type AppColors = {
  [K in keyof typeof lightColors]: string;
};

export function useAppTheme() {
  const isDark = useColorScheme() === "dark";
  return { colors: (isDark ? darkColors : lightColors) as AppColors, isDark };
}

export const fonts = {
  serif: Platform.OS === "web" ? "Georgia, serif" : "Georgia",
  sans: Platform.OS === "web" ? "system-ui, sans-serif" : undefined,
};

export function glassSurface(colors: AppColors) {
  return {
    borderRadius: 24,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    padding: 22,
    elevation: 5,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 24 },
    shadowOpacity: 1,
    shadowRadius: 35,
    ...(Platform.OS === "web"
      ? ({
          boxShadow: `0 24px 70px ${colors.shadow}, inset 0 1px 0 rgba(255,255,255,0.82)`,
          backdropFilter: "blur(24px) saturate(125%)",
          WebkitBackdropFilter: "blur(24px) saturate(125%)",
        } as object)
      : null),
  };
}
