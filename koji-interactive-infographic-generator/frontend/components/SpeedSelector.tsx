import React from "react";
import { Pressable, Text, View } from "react-native";
import type { SpeedMode } from "../App";
import { useAppTheme } from "../theme";

interface Props {
  options: readonly { id: SpeedMode; label: string; desc: string }[];
  value: SpeedMode;
  disabled: boolean;
  onChange: (value: SpeedMode) => void;
}
export default function SpeedSelector({ options, value, disabled, onChange }: Props) {
  const { colors } = useAppTheme();
  return <View style={{ flexDirection: "row", gap: 8, flexGrow: 1, flexBasis: 200, maxWidth: 280 }}>
    {options.map(option => {
      const selected = value === option.id;
      const color = selected ? colors.onButton : colors.text;
      return <Pressable key={option.id} accessibilityRole="button" accessibilityLabel={option.label + ": " + option.desc}
        accessibilityState={{ selected, disabled }} aria-pressed={selected} disabled={disabled} onPress={() => onChange(option.id)}
        style={({ pressed }) => ({ flex: 1, minWidth: 0, minHeight: 44, paddingHorizontal: 12, paddingVertical: 10, borderRadius: 8,
          borderWidth: 1, borderColor: selected ? colors.buttonBackground : colors.textDim,
          backgroundColor: selected ? colors.buttonBackground : colors.surface,
          flexDirection: "row", gap: 6, alignItems: "center", justifyContent: "center", opacity: disabled ? .55 : pressed ? .65 : 1 })}>
        <Text style={{ color, fontSize: 13, fontWeight: "600" }}>{option.label}</Text>
      </Pressable>;
    })}
  </View>;
}
