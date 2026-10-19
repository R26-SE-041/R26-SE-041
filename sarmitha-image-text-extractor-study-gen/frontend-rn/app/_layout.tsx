import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { Platform, View } from "react-native";
import { useEffect } from "react";
import { editorialWebStyles } from "@/lib/web-style";
import AuthProvider from "@/components/AuthProvider";
import { useAppTheme } from "@/theme";
import ToolkitNavigation from "@/components/ToolkitNavigation";

export default function RootLayout() {
  const { colors, isDark } = useAppTheme();
  useEffect(() => {
    if (Platform.OS !== "web") return;
    const style = document.createElement("style");
    style.id = "editorial-web-styles";
    style.textContent = editorialWebStyles;
    document.head.appendChild(style);
    document.title = "Sinhala OCR — A clearer way to read your notes";
    let description = document.querySelector<HTMLMetaElement>('meta[name="description"]');
    if (!description) {
      description = document.createElement("meta");
      description.name = "description";
      document.head.appendChild(description);
    }
    description.content = "Enhance handwritten Sinhala notes, extract editable text, and translate into Tamil and English.";
    return () => style.remove();
  }, []);
  return (
    <AuthProvider><View style={{ flex: 1, backgroundColor: colors.background }}>
      <ToolkitNavigation componentName="Sinhala OCR" background={colors.background} color={colors.text} border={colors.border} />
      <StatusBar style={isDark ? "light" : "dark"} />
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: colors.background },
          animation: "fade",
        }}
      />
    </View></AuthProvider>
  );
}
