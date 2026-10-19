import React from "react";
import { Text, View } from "react-native";
import { answerBlocks } from "../answerBlocks";
import { bodyFont, useAppTheme } from "../theme";

function inline(text: string) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, index) => part.startsWith("**") && part.endsWith("**")
    ? <Text key={index} style={{ fontWeight: "600" }}>{part.slice(2, -2)}</Text> : part);
}

export default function StructuredAnswer({ answer }: { answer: string }) {
  const { colors } = useAppTheme();
  return <View style={{ gap: 10 }}>
    {answerBlocks(answer).map((block, index) => <View key={index} style={{ flexDirection: "row", gap: 10, minWidth: 0, marginTop: block.kind === "heading" && index > 0 ? 8 : 0 }}>
      {block.kind === "list" && <Text style={{ color: colors.textMuted, fontFamily: bodyFont, lineHeight: 24, minWidth: 18 }}>{block.marker}</Text>}
      <Text selectable accessibilityRole={block.kind === "heading" ? "header" : undefined} style={{ flex: 1, minWidth: 0, fontFamily: bodyFont, color: block.kind === "heading" ? colors.text : colors.textMuted, fontSize: block.kind === "heading" ? 16 : 14, fontWeight: block.kind === "heading" ? "600" : "400", lineHeight: 24 }}>{inline(block.text)}</Text>
    </View>)}
  </View>;
}
