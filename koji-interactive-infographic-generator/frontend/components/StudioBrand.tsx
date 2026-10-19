import React from "react";
import { Text, View } from "react-native";
import { displayFont, useAppTheme } from "../theme";
import LearnXHomeLink from "./LearnXHomeLink";

export default function StudioBrand({ compact = false }: { compact?: boolean }) {
  const { colors } = useAppTheme();
  return <View style={{ flexDirection: "row", alignItems: "center", gap: 16 }}>
    <LearnXHomeLink color={colors.text} />
    {!compact && <Text style={{ color: colors.textMuted, fontFamily: displayFont, fontSize: 12, borderLeftWidth: 1, borderColor: colors.border, paddingLeft: 16 }}>Visual learning studio</Text>}
  </View>;
}
