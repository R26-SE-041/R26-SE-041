import type { AnatomyAnnotation } from "../App";
export const LABEL_HEIGHT = 36;
export const LABEL_FONT_SIZE = 17;
export const LABEL_PADDING = 14;
export const labelWidth = (name: string) => Math.min(270, Math.max(110, name.length * 10 + LABEL_PADDING * 2));
export const clamp = (value: number, min = 0, max = 1) => Math.max(min, Math.min(max, value));
export function annotationGeometry(item: AnatomyAnnotation) {
  const width = labelWidth(item.label);
  const x = clamp(item.label_x, 0, 1 - width / 1000) * 1000;
  const y = clamp(item.label_y, LABEL_HEIGHT / 2000, 1 - LABEL_HEIGHT / 2000) * 1000;
  const ax = clamp(item.anchor_x) * 1000, ay = clamp(item.anchor_y) * 1000;
  const endX = x + (ax > x + width / 2 ? width : 0);
  const angle = Math.atan2(ay - y, ax - endX);
  const backX = ax - 13 * Math.cos(angle), backY = ay - 13 * Math.sin(angle);
  const arrow = [[ax, ay], [backX + 5 * Math.sin(angle), backY - 5 * Math.cos(angle)], [backX - 5 * Math.sin(angle), backY + 5 * Math.cos(angle)]];
  return { x, y, ax, ay, endX, width, arrow: arrow.map(p => p.join(",")).join(" ") };
}
