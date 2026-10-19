import React from "react";
import { Linking, Pressable, Text } from "react-native";

export default function LearnXHomeLink({ color, fontFamily }: { color: string; fontFamily?: string }) {
  return <Pressable accessibilityRole="link" accessibilityLabel="LearnX home — all learning tools"
    onPress={() => Linking.openURL("https://biolearnx-dashboard.vercel.app/")}>
    <Text selectable={false} style={{ color, fontFamily, fontSize: 24, fontWeight: "700", letterSpacing: -.8 }}>learnX</Text>
  </Pressable>;
}
