import React, { useEffect, useMemo, useRef, useState } from "react";
import { Image, PanResponder, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import type { AnatomyAnnotation } from "../App";
import AnatomyOverlay from "./AnatomyOverlay";
import { annotationGeometry, clamp, labelWidth } from "./annotationGeometry";
import { useAppTheme } from "../theme";
interface Props { imageBase64: string; annotations: AnatomyAnnotation[]; onChange: (items: AnatomyAnnotation[]) => void; commitRef?: React.MutableRefObject<(() => void) | null> }
export default function AnnotationEditor({ imageBase64, annotations, onChange, commitRef }: Props) {
  const { colors } = useAppTheme();
  const [selected, setSelected] = useState<string | null>(annotations[0]?.structure_id ?? null);
  const [move, setMove] = useState<"target" | "label">("target");
  const [size, setSize] = useState({ width: 1, height: 1 });
  const [draft, setDraft] = useState(annotations);
  const latest = useRef(draft); latest.current = draft;
  const selectedRef = useRef(selected); selectedRef.current = selected;
  useEffect(() => { setDraft(annotations); }, [annotations]);
  const commit = (items: AnatomyAnnotation[]) => { setDraft(items); onChange(items); };
  const edit = (id: string, patch: Partial<AnatomyAnnotation>, persist = true) => {
    const items = latest.current.map(a => a.structure_id === id ? { ...a, ...patch, user_edited: true } : a);
    latest.current = items; setDraft(items); if (persist) onChange(items);
  };
  const responder = useMemo(() => PanResponder.create({
    onStartShouldSetPanResponder: () => true,
    onMoveShouldSetPanResponder: () => true,
    onPanResponderGrant: event => {
      const x = clamp(event.nativeEvent.locationX / size.width), y = clamp(event.nativeEvent.locationY / size.height);
      const hit = latest.current.find(a => { const g = annotationGeometry(a); return Math.hypot(a.anchor_x-x,a.anchor_y-y)<0.04 || (x*1000>=g.x && x*1000<=g.x+g.width && Math.abs(y*1000-g.y)<22); });
      const id = hit?.structure_id ?? selectedRef.current; if (!id) return;
      selectedRef.current = id; setSelected(id);
      const item = latest.current.find(a => a.structure_id === id)!;
      edit(id, move === "target" ? { anchor_x:x, anchor_y:y } : { label_x:clamp(x,0,1-labelWidth(item.label)/1000), label_y:clamp(y,0.018,0.982) }, false);
    },
    onPanResponderMove: event => {
      const id = selectedRef.current; if (!id) return;
      const x = clamp(event.nativeEvent.locationX / size.width), y = clamp(event.nativeEvent.locationY / size.height);
      const item = latest.current.find(a => a.structure_id === id); if (!item) return;
      edit(id, move === "target" ? { anchor_x:x, anchor_y:y } : { label_x:clamp(x,0,1-labelWidth(item.label)/1000), label_y:clamp(y,0.018,0.982) }, false);
    },
    onPanResponderRelease: () => onChange(latest.current),
    onPanResponderTerminate: () => onChange(latest.current),
  }), [size, move, onChange]);
  if (commitRef) commitRef.current = () => commit(latest.current.map(a => ({ ...a, label: a.label.trim() || "New label" })));
  const item = draft.find(a => a.structure_id === selected);
  const button = { borderWidth:1, borderColor:colors.border, borderRadius:9, padding:9 };
  return <View style={{ gap:12 }}>
    <Text style={{ color:colors.textMuted }}>Select a label, then drag its target or label position. Edits are saved with this image.</Text>
    <View style={{ flexDirection:"row", flexWrap:"wrap", gap:8 }}>{draft.map(a => <Pressable key={a.structure_id} onPress={() => setSelected(a.structure_id)} style={[button,{ borderColor:selected===a.structure_id?colors.primaryBright:colors.border }]}><Text style={{ color:colors.text }}>{a.label}</Text></Pressable>)}</View>
    <View style={{ flexDirection:"row", flexWrap:"wrap", gap:8 }}>
      <Pressable style={button} onPress={() => { const id = "manual." + Date.now().toString(36) + Math.random().toString(36).slice(2,6); commit([...latest.current,{structure_id:id,label:"New label",anchor_x:0.5,anchor_y:0.5,label_x:0.05,label_y:0.1,confidence:0,verified:false,user_edited:true,source:"manual"}]); setSelected(id); }}><Text style={{ color:colors.text }}>Add label</Text></Pressable>
      {item && <><Pressable style={button} onPress={() => { commit(latest.current.filter(a => a.structure_id!==selected)); setSelected(null); }}><Text style={{ color:colors.danger }}>Delete label</Text></Pressable>
      <Pressable style={button} onPress={() => setMove("target")}><Text style={{ color:move==="target"?colors.primaryBright:colors.text }}>Move arrow target</Text></Pressable>
      <Pressable style={button} onPress={() => setMove("label")}><Text style={{ color:move==="label"?colors.primaryBright:colors.text }}>Move label</Text></Pressable></>}
    </View>
    {item && <TextInput accessibilityLabel="Label name" value={item.label} maxLength={80} onChangeText={label => edit(item.structure_id,{label},false)} onBlur={() => { if (!latest.current.find(a=>a.structure_id===selected)?.label.trim()) edit(item.structure_id,{label:"New label"},false); onChange(latest.current); }} style={{ color:colors.text,borderWidth:1,borderColor:colors.border,borderRadius:9,padding:12 }} />}
    {item && <Pressable style={button} onPress={() => edit(item.structure_id, { label: item.label.trim() || "New label" })}><Text style={{ color: colors.text }}>Save name</Text></Pressable>}
    <View accessibilityLabel="Label editing canvas" {...responder.panHandlers} onLayout={e=>setSize(e.nativeEvent.layout)} style={{ width:"100%",aspectRatio:1,backgroundColor:"white" }}>
      <Image source={{uri:"data:image/png;base64,"+imageBase64}} style={StyleSheet.absoluteFill} resizeMode="contain" />
      <AnatomyOverlay annotations={draft} selectedStructureId={selected} />
    </View>
  </View>;
}
