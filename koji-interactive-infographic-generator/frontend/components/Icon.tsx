import React from "react";
import Svg, { Circle, Line, Path, Polyline, Rect } from "react-native-svg";

export type IconName =
  | "activity"
  | "arrow-left"
  | "bolt"
  | "book"
  | "box-select"
  | "check"
  | "clock"
  | "cube"
  | "download"
  | "help"
  | "layers"
  | "minus"
  | "moon"
  | "plus"
  | "refresh"
  | "rocket"
  | "search"
  | "sun"
  | "tag"
  | "target"
  | "wand";

interface IconProps {
  color?: string;
  name: IconName;
  size?: number;
  strokeWidth?: number;
}

export default function Icon({ color = "currentColor", name, size = 18, strokeWidth = 2 }: IconProps) {
  const common = { fill: "none", stroke: color, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, strokeWidth };
  return (
    <Svg accessibilityElementsHidden focusable={false} height={size} viewBox="0 0 24 24" width={size}>
      {name === "activity" && <Path {...common} d="M3 12h4l2.5-7 5 14 2.5-7h4" />}
      {name === "arrow-left" && <><Line {...common} x1="20" x2="4" y1="12" y2="12" /><Polyline {...common} points="10 18 4 12 10 6" /></>}
      {name === "bolt" && <Path {...common} d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z" />}
      {name === "book" && <><Path {...common} d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><Path {...common} d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z" /></>}
      {name === "box-select" && <><Rect {...common} height="14" rx="1" width="14" x="5" y="5" /><Path {...common} d="M9 2H2v7M15 22h7v-7" /></>}
      {name === "check" && <Polyline {...common} points="20 6 9 17 4 12" />}
      {name === "clock" && <><Circle {...common} cx="12" cy="12" r="9" /><Polyline {...common} points="12 7 12 12 15 14" /></>}
      {name === "cube" && <><Path {...common} d="m12 2 9 5-9 5-9-5 9-5Z" /><Path {...common} d="m3 7 9 5 9-5M3 7v10l9 5 9-5V7M12 12v10" /></>}
      {name === "download" && <><Path {...common} d="M12 3v12" /><Polyline {...common} points="7 10 12 15 17 10" /><Path {...common} d="M5 21h14" /></>}
      {name === "help" && <><Circle {...common} cx="12" cy="12" r="9" /><Path {...common} d="M9.5 9a2.7 2.7 0 1 1 4.2 2.3c-1 .6-1.7 1.1-1.7 2.2" /><Circle cx="12" cy="17" fill={color} r="1" /></>}
      {name === "layers" && <><Path {...common} d="m12 2 9 5-9 5-9-5 9-5Z" /><Path {...common} d="m3 12 9 5 9-5M3 17l9 5 9-5" /></>}
      {name === "minus" && <Line {...common} x1="5" x2="19" y1="12" y2="12" />}
      {name === "moon" && <Path {...common} d="M20 15.5A8.5 8.5 0 0 1 8.5 4 9 9 0 1 0 20 15.5Z" />}
      {name === "plus" && <><Line {...common} x1="12" x2="12" y1="5" y2="19" /><Line {...common} x1="5" x2="19" y1="12" y2="12" /></>}
      {name === "refresh" && <><Path {...common} d="M20 7v5h-5" /><Path {...common} d="M4 17v-5h5" /><Path {...common} d="M7.8 7.8A7 7 0 0 1 20 12M4 12a7 7 0 0 0 12.2 4.2" /></>}
      {name === "rocket" && <><Path {...common} d="M14 5c3-3 6-3 6-3s0 3-3 6l-5 5-4-4 6-4Z" /><Path {...common} d="m8 9-4 1-2 3 6 1M12 13l-1 6-3 2-1-6" /><Circle {...common} cx="16" cy="6" r="1" /></>}
      {name === "search" && <><Circle {...common} cx="11" cy="11" r="7" /><Line {...common} x1="16" x2="21" y1="16" y2="21" /></>}
      {name === "sun" && <><Circle {...common} cx="12" cy="12" r="4" /><Path {...common} d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>}
      {name === "tag" && <><Path {...common} d="M20 13 13 20 4 11V4h7l9 9Z" /><Circle {...common} cx="8.5" cy="8.5" r="1" /></>}
      {name === "target" && <><Circle {...common} cx="12" cy="12" r="9" /><Circle {...common} cx="12" cy="12" r="4" /><Circle cx="12" cy="12" fill={color} r="1.5" /></>}
      {name === "wand" && <><Path {...common} d="m4 20 10-10" /><Path {...common} d="m13 4 1-2 1 2 2 1-2 1-1 2-1-2-2-1 2-1ZM18 13l1-2 1 2 2 1-2 1-1 2-1-2-2-1 2-1Z" /></>}
    </Svg>
  );
}

export function StatusDot({ color, size = 9 }: { color: string; size?: number }) {
  return <Svg accessibilityElementsHidden height={size} viewBox="0 0 10 10" width={size}><Circle cx="5" cy="5" fill={color} r="5" /></Svg>;
}
