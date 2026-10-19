import React from "react";
import { Text, View } from "react-native";
import ThreeDViewer from "./ThreeDViewer";
import { ModelGalleryProps, useSavedModels } from "./useSavedModels";
import { useAppTheme } from "../theme";
import HistoryCardMenu from "./HistoryCardMenu";

export default function ModelGallery(props: ModelGalleryProps) {
  const { colors } = useAppTheme();
  const { models, error } = useSavedModels(props);
  return <View style={{ gap: 16 }}>{error && <Text style={{ color: colors.danger }}>{error}</Text>}{models.filter(model => model.title.toLowerCase().includes(props.query.toLowerCase())).map(model => <View key={model.modelKey} style={{ gap: 10 }}><View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}><Text style={{ color: colors.text, flex: 1 }}>{model.title}</Text><HistoryCardMenu title={model.title} disabled={props.busy} trashed={props.trashed} onOpen={() => props.onOpen(model)} onContinue={props.onContinue ? () => props.onContinue!(model) : undefined} onRename={() => props.onRename(model)} onDelete={() => props.onDelete(model)} onRestore={() => props.onRestore(model)} /></View><ThreeDViewer glbBase64={model.glbBase64} modelUrl={model.modelUrl} modelKey={model.modelKey} active={props.active} /></View>)}</View>;
}
