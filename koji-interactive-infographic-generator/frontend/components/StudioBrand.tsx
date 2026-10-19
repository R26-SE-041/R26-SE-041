import React from "react";
import { Platform, Text, View } from "react-native";
import { displayFont, useAppTheme } from "../theme";

export default function StudioBrand({ compact = false }: { compact?: boolean }) {
  const { colors } = useAppTheme();
  return <View style={{ flexDirection: "row", alignItems: "center", gap: 16 }}>
    <Text {...(Platform.OS === "web" ? { dataSet: { studioBrand: "true" } } : {})} accessibilityLabel="learnX" style={{ color: colors.text, fontFamily: displayFont, fontSize: 25, lineHeight: 30, fontWeight: "700", letterSpacing: -1 }}>LEARNX</Text>
    {!compact && <Text style={{ color: colors.textMuted, fontFamily: displayFont, fontSize: 12, borderLeftWidth: 1, borderColor: colors.border, paddingLeft: 16 }}>Visual learning studio</Text>}
  </View>;
}
