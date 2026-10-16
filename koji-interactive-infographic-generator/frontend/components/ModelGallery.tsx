import React from "react";
import { Pressable, Text, View } from "react-native";
import ThreeDViewer from "./ThreeDViewer";
import { ModelGalleryProps, useSavedModels } from "./useSavedModels";
import { useAppTheme } from "../theme";

export default function ModelGallery(props: ModelGalleryProps) {
  const { colors } = useAppTheme();
  const { models, error } = useSavedModels(props);
  return <View style={{ gap: 16 }}>{error && <Text style={{ color: colors.danger }}>{error}</Text>}{models.filter(model => model.title.toLowerCase().includes(props.query.toLowerCase())).map(model => <View key={model.modelKey} style={{ gap: 10 }}><Text style={{ color: colors.text }}>{model.title}</Text><ThreeDViewer glbBase64={model.glbBase64} modelUrl={model.modelUrl} modelKey={model.modelKey} active={props.active} /><Pressable onPress={() => props.onOpen(model)}><Text style={{ color: colors.text }}>Open creation</Text></Pressable></View>)}</View>;
}
