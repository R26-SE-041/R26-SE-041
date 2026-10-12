import React from "react";
import { Platform, Text, type TextProps } from "react-native";

/** Word reveals follow the public site's 800ms easing; native stays static. */
export default function EditorialHeadline({ children, ...props }: Omit<TextProps, "children"> & { children: string }) {
  if (Platform.OS !== "web") return <Text {...props}>{children}</Text>;
  let wordIndex = 0;
  return <Text {...props} accessibilityLabel={children}>
    {children.split(/(\s+)/).map((part, index) => /^\s+$/.test(part)
      ? part
      : <Text key={index} {...{ dataSet: { revealWord: "true" } }} style={{ animationDelay: `${wordIndex++ * 35}ms` } as TextProps["style"]}>{part}</Text>)}
  </Text>;
}
