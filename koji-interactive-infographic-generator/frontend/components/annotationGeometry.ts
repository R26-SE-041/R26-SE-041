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

/** Hit-test in screen pixels so arrow handles stay usable at any canvas size. */
export function annotationHit(items: AnatomyAnnotation[], x: number, y: number, width: number, height: number) {
  const visible = items.filter(item => item.verified || item.user_edited);
  for (const item of [...visible].reverse()) {
    const g = annotationGeometry(item);
    if (x >= g.x / 1000 && x <= (g.x + g.width) / 1000 && Math.abs(y - g.y / 1000) <= LABEL_HEIGHT / 2000) {
      return { id: item.structure_id, part: "label" as const };
    }
  }
  let nearest: { id: string; part: "target"; distance: number } | undefined;
  for (const item of visible) {
    const g = annotationGeometry(item);
    const ax = g.ax / 1000 * width, ay = g.ay / 1000 * height;
    const bx = g.endX / 1000 * width, by = g.y / 1000 * height;
    const px = x * width, py = y * height;
    const length = (bx - ax) ** 2 + (by - ay) ** 2;
    const t = length ? clamp(((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / length) : 0;
    const distance = Math.hypot(px - ax - t * (bx - ax), py - ay - t * (by - ay));
    if (distance <= 12 && (!nearest || distance < nearest.distance)) nearest = { id: item.structure_id, part: "target", distance };
  }
  return nearest;
}
