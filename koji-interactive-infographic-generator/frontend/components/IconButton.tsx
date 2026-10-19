import React from "react";
import { Platform, Pressable } from "react-native";
import Icon, { type IconName } from "./Icon";
import { useAppTheme } from "../theme";

interface Props {
  label: string;
  icon: IconName;
  onPress: () => void;
  disabled?: boolean;
  selected?: boolean;
}

/** Equal touch targets, discoverable labels, and one shared SVG treatment. */
export default function IconButton({ label, icon, onPress, disabled = false, selected }: Props) {
  const { colors } = useAppTheme();
  return <Pressable
    {...(Platform.OS === "web" ? { dataSet: { tooltip: label } } : {})}
    accessibilityRole="button" accessibilityLabel={label}
    accessibilityState={{ disabled, ...(selected === undefined ? {} : { selected }) }}
    aria-pressed={selected} disabled={disabled} onPress={onPress}
    style={({ pressed }) => ({
      width: 44, height: 44, flexShrink: 0, alignItems: "center", justifyContent: "center",
      borderRadius: 8, borderWidth: 1, borderColor: selected ? colors.buttonBackground : colors.border,
      backgroundColor: selected ? colors.buttonBackground : colors.surface,
      opacity: disabled ? .4 : pressed ? .7 : 1,
    })}>
    <Icon name={icon} size={20} strokeWidth={1.75} color={selected ? colors.onButton : colors.text} />
  </Pressable>;
}
