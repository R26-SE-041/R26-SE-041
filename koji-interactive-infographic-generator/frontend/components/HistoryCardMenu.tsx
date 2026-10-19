import React, { useState } from "react";
import { Platform, Pressable, Text, View } from "react-native";
import ArchiveDialog from "./ArchiveDialog";
import Icon, { type IconName } from "./Icon";
import { useAppTheme } from "../theme";

interface Props {
  title: string;
  disabled?: boolean;
  trashed?: boolean;
  onOpen: () => void;
  onContinue?: () => void;
  onRename: () => void;
  onDelete: () => void;
  onRestore?: () => void;
}

/** One accessible action menu for images, sketches and saved 3D models. */
export default function HistoryCardMenu(props: Props) {
  const { colors } = useAppTheme();
  const [open, setOpen] = useState(false);
  const action = (label: string, icon: IconName, run: () => void, destructive = false) => <Pressable key={label} accessibilityRole="button" disabled={props.disabled}
    onPress={() => { setOpen(false); run(); }}
    style={{ minHeight: 48, flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 12, borderRadius: 8 }}>
    <Icon name={icon} color={destructive ? colors.danger : colors.text} size={19} />
    <Text style={{ color: destructive ? colors.danger : colors.text, fontSize: 15 }}>{label}</Text>
  </Pressable>;
  return <View style={{ alignSelf: "flex-end" }}>
    <Pressable accessibilityRole="button" accessibilityLabel={`More actions for ${props.title}`} accessibilityState={{ expanded: open, disabled: props.disabled }}
      {...(Platform.OS === "web" ? { dataSet: { tooltip: "More actions" } } : {})}
      disabled={props.disabled} onPress={() => setOpen(true)}
      style={{ width: 44, height: 44, alignItems: "center", justifyContent: "center", borderRadius: 8 }}>
      <Icon name="more" color={colors.text} size={22} />
    </Pressable>
    {open && <ArchiveDialog title="Creation actions" busy={Boolean(props.disabled)} onClose={() => setOpen(false)}>
      <Text numberOfLines={2} style={{ color: colors.textMuted, fontSize: 14, lineHeight: 22 }}>{props.title}</Text>
      <View style={{ gap: 4 }}>
        {props.trashed ? <>
          {props.onRestore && action("Restore", "undo", props.onRestore)}
          {action("Delete permanently", "trash", props.onDelete, true)}
        </> : <>
          {action("Open", "eye", props.onOpen)}
          {props.onContinue && action("Continue in chat", "message-plus", props.onContinue)}
          {action("Rename", "pencil", props.onRename)}
          {action("Delete", "trash", props.onDelete, true)}
        </>}
      </View>
    </ArchiveDialog>}
  </View>;
}
