import React from "react";
import { Linking, Platform, Pressable, Text, View } from "react-native";

export default function LearnXHomeLink({ color, size = 26 }: { color: string; size?: number }) {
  const type = { color, fontFamily: Platform.select({ ios: "Arial", default: "sans-serif" }), fontSize: size, lineHeight: size, letterSpacing: -.9 };
  return <Pressable accessibilityRole="link" accessibilityLabel="LearnX home — all learning tools"
    onPress={() => Linking.openURL("https://biolearnx-dashboard.vercel.app/")}>
    <View style={{ flexDirection: "row", alignItems: "center" }}>
      <Text selectable={false} style={[type, { fontWeight: "800" }]}>LEARN</Text>
      <Text selectable={false} style={[type, { fontWeight: "400", marginLeft: 1, transform: [{ skewX: "-11deg" }] }]}>X</Text>
    </View>
  </Pressable>;
}
