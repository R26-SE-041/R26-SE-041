import type { AnatomyAnnotation } from "../App";

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
  return `eduvision-${safeOrgan || "anatomy"}`;
}

export function buildLabeledSvg(imageBase64: string, annotations: AnatomyAnnotation[]): string {
  const labels = annotations.map((item) => {
    const anchorX = item.anchor_x * SCALE;
    const anchorY = item.anchor_y * SCALE;
    const labelX = item.label_x * SCALE;
    const labelY = item.label_y * SCALE;
    const labelWidth = Math.min(255, Math.max(105, item.label.length * 10 + 28));
    const lineEndX = labelX + (labelX < anchorX ? labelWidth : 0);
    return [
      `<line x1="${anchorX}" y1="${anchorY}" x2="${lineEndX}" y2="${labelY}" stroke="#0891b2" stroke-width="3"/>`,
      `<circle cx="${anchorX}" cy="${anchorY}" r="7" fill="#06b6d4"/>`,
      `<rect x="${labelX}" y="${labelY - 17}" width="${labelWidth}" height="34" rx="8" fill="#083344" fill-opacity="0.94"/>`,
      `<text x="${labelX + 12}" y="${labelY + 6}" fill="#ffffff" font-family="Arial, sans-serif" font-size="18" font-weight="700">${escapeXml(item.label)}</text>`,
    ].join("");
  }).join("");

  return `<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1000" viewBox="0 0 ${SCALE} ${SCALE}"><image width="${SCALE}" height="${SCALE}" href="data:image/png;base64,${imageBase64}" preserveAspectRatio="none"/>${labels}</svg>`;
}
