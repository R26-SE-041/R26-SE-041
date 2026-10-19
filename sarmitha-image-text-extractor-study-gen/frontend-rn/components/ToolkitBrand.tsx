import React from "react";
import { Linking, Pressable, Text } from "react-native";

export default function ToolkitBrand() {
  return <Pressable accessibilityRole="link" accessibilityLabel="LearnX home — all learning tools"
    onPress={() => Linking.openURL("https://biolearnx-dashboard.vercel.app/")}>
    <Text selectable={false} style={{ color: "#141413", fontSize: 18, fontWeight: "800", letterSpacing: -.6 }}>LearnX</Text>
  </Pressable>;
}
