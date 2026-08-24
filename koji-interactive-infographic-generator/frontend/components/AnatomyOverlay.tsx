import React from "react";
import Svg, { Circle, Line, Polygon, Rect, Text as SvgText } from "react-native-svg";
import { StyleSheet, View } from "react-native";
import type { AnatomyAnnotation } from "../App";

interface AnatomyOverlayProps {
  annotations: AnatomyAnnotation[];
  selectedStructureId?: string | null;
  showGridPrompts?: boolean;
}

const SCALE = 1000;

// Label box dimensions in SVG units (viewBox = 0..1000).
// _LABEL_HEIGHT must match the backend _LABEL_HEIGHT * SCALE convention.
const LABEL_BOX_HEIGHT = 36;
const LABEL_BOX_HALF   = LABEL_BOX_HEIGHT / 2;
const LABEL_FONT_SIZE  = 17;
// Approximate character width for the proportional font used.
const CHAR_WIDTH = 10;
const LABEL_MIN_WIDTH = 110;
const LABEL_MAX_WIDTH = 270;
const LABEL_PADDING_X = 14;

function labelBoxWidth(label: string): number {
  return Math.min(LABEL_MAX_WIDTH, Math.max(LABEL_MIN_WIDTH, label.length * CHAR_WIDTH + LABEL_PADDING_X * 2));
}

export default function AnatomyOverlay({ annotations, selectedStructureId, showGridPrompts = true }: AnatomyOverlayProps) {
  // Defense-in-depth: only render annotations that passed all quality gates.
  // App.tsx already filters upstream, but this component should be self-protecting.
  const verified = annotations.filter((item) => item.verified === true);
  return (
    <View pointerEvents="none" style={StyleSheet.absoluteFill}>
      <Svg
        height="100%"
        preserveAspectRatio="none"
        viewBox={`0 0 ${SCALE} ${SCALE}`}
        width="100%"
      >
        {showGridPrompts && Array.from({ length: 7 }, (_, index) => {
          const position = index / 6 * SCALE;
          return (
            <React.Fragment key={`grid-line-${index}`}>
              <Line stroke="#0ea5e9" strokeOpacity={0.18} strokeWidth={1} x1={position} x2={position} y1={0} y2={SCALE} />
              <Line stroke="#0ea5e9" strokeOpacity={0.18} strokeWidth={1} x1={0} x2={SCALE} y1={position} y2={position} />
            </React.Fragment>
          );
        })}
        {showGridPrompts && Array.from({ length: 16 }, (_, index) => {
          const row = Math.floor(index / 4) + 1;
          const column = (index % 4) + 1;
          const x = (column + 0.5) / 6 * SCALE;
          const y = (row + 0.5) / 6 * SCALE;
          return (
            <React.Fragment key={`grid-prompt-${index}`}>
              <Circle cx={x} cy={y} fill="#0ea5e9" fillOpacity={0.28} r={7} stroke="#ffffff" strokeWidth={1.5} />
              <Polygon fill="#0ea5e9" fillOpacity={0.9} points={`${x},${y - 16} ${x - 6},${y - 5} ${x + 6},${y - 5}`} />
            </React.Fragment>
          );
        })}
        {verified.map((item) => {
          const anchorX   = item.anchor_x * SCALE;
          const anchorY   = item.anchor_y * SCALE;
          // label_y from the backend is the vertical *center* of the label box.
          const labelCX   = item.label_x * SCALE;
          const labelCY   = item.label_y * SCALE;
          const boxTop    = labelCY - LABEL_BOX_HALF;
          const selected  = selectedStructureId === item.structure_id;
          const boxWidth  = labelBoxWidth(item.label);

          // Callout line: anchor point → center of nearest horizontal edge of label box.
          // If label is to the left of anchor, line connects to label's right edge center.
          // If label is to the right of anchor, line connects to label's left edge center.
          const labelIsLeft  = labelCX < anchorX;
          const lineX2       = labelIsLeft ? labelCX + boxWidth : labelCX;
          const lineY2       = labelCY; // Exact vertical center of the label box

          return (
            <React.Fragment key={item.structure_id}>
              {/* Callout line from anchor dot on organ to center of label box edge */}
              <Line
                stroke={selected ? "#f59e0b" : "#0891b2"}
                strokeWidth={selected ? 4 : 2}
                strokeDasharray={selected ? undefined : undefined}
                x1={anchorX}
                x2={lineX2}
                y1={anchorY}
                y2={lineY2}
              />
              {/* Anchor dot over the anatomical structure */}
              <Circle
                cx={anchorX}
                cy={anchorY}
                fill={selected ? "#f59e0b" : "#06b6d4"}
                r={selected ? 9 : 6}
                stroke="#ffffff"
                strokeWidth={selected ? 2.5 : 1.5}
              />
              {/* Small connection dot at label box edge */}
              <Circle
                cx={lineX2}
                cy={lineY2}
                fill={selected ? "#f59e0b" : "#0891b2"}
                r={selected ? 4 : 3}
              />
              {/* Label background box */}
              <Rect
                fill={selected ? "#78350f" : "#083344"}
                height={LABEL_BOX_HEIGHT}
                opacity={0.94}
                rx={8}
                width={boxWidth}
                x={labelCX}
                y={boxTop}
              />
              {/* Label text */}
              <SvgText
                fill="#ffffff"
                fontSize={LABEL_FONT_SIZE}
                fontWeight="700"
                x={labelCX + LABEL_PADDING_X}
                y={labelCY + LABEL_FONT_SIZE * 0.36}
              >
                {item.label}
              </SvgText>
            </React.Fragment>
          );
        })}
      </Svg>
    </View>
  );
}
