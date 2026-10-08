import type { AnatomyAnnotation } from "../App";
import { annotationGeometry, LABEL_HEIGHT, LABEL_FONT_SIZE, LABEL_PADDING } from "./annotationGeometry";

const SCALE = 1000;

function escapeXml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

export function exportFileStem(organ?: string): string {
  const safeOrgan = (organ || "anatomy").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return `learnX-${safeOrgan || "anatomy"}`;
}

export function buildLabeledSvg(imageBase64: string, annotations: AnatomyAnnotation[]): string {
  const labels = annotations.map((item) => {
    const { ax: anchorX, ay: anchorY, x: labelX, y: labelY, width: labelWidth, endX: lineEndX, arrow } = annotationGeometry(item);
    return [
      `<line x1="${anchorX}" y1="${anchorY}" x2="${lineEndX}" y2="${labelY}" stroke="#0891b2" stroke-width="3"/>`,
      `<polygon points="${arrow}" fill="#0891b2"/>`,
      `<circle cx="${anchorX}" cy="${anchorY}" r="3" fill="#06b6d4"/>`,
      `<rect x="${labelX}" y="${labelY - LABEL_HEIGHT/2}" width="${labelWidth}" height="${LABEL_HEIGHT}" rx="8" fill="#083344" fill-opacity="0.94"/>`,
      `<text x="${labelX + LABEL_PADDING}" y="${labelY + LABEL_FONT_SIZE * 0.36}" fill="#ffffff" font-family="Arial, sans-serif" font-size="${LABEL_FONT_SIZE}" font-weight="700">${escapeXml(item.label)}</text>`,
    ].join("");
  }).join("");

  return `<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1000" viewBox="0 0 ${SCALE} ${SCALE}"><image width="${SCALE}" height="${SCALE}" href="data:image/png;base64,${imageBase64}" preserveAspectRatio="none"/>${labels}</svg>`;
}
