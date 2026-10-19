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
  variant?: "outlined" | "plain";
  filled?: boolean;
}

/** Equal touch targets, discoverable labels, and one shared SVG treatment. */
export default function IconButton({ label, icon, onPress, disabled = false, selected, variant = "outlined", filled = false }: Props) {
  const { colors } = useAppTheme();
  return <Pressable
    {...(Platform.OS === "web" ? { dataSet: { tooltip: label, ...(variant === "plain" ? { iconOnly: "true" } : {}) } } : {})}
    accessibilityRole="button" accessibilityLabel={label}
    accessibilityState={{ disabled, ...(selected === undefined ? {} : { selected }) }}
    aria-pressed={selected} disabled={disabled} onPress={onPress}
    style={({ pressed }) => ({
      width: 44, height: 44, flexShrink: 0, alignItems: "center", justifyContent: "center",
      borderRadius: 8, borderWidth: variant === "plain" ? 0 : 1, borderColor: selected ? colors.buttonBackground : colors.border,
      backgroundColor: variant === "plain" ? "transparent" : selected ? colors.buttonBackground : colors.surface,
      opacity: disabled ? .4 : pressed ? .7 : 1,
    })}>
    <Icon name={icon} filled={filled} size={20} strokeWidth={1.75} color={variant === "plain" ? selected ? colors.text : colors.textMuted : selected ? colors.onButton : colors.text} />
  </Pressable>;
}
