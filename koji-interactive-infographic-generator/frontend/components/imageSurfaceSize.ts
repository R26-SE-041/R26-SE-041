/** Fit the entire image without adding letterbox space to its coordinate surface. */
export function imageSurfaceSize(availableWidth: number, aspectRatio: number, maxHeight = 720) {
  const ratio = Number.isFinite(aspectRatio) && aspectRatio > 0 ? aspectRatio : 1;
  const width = Math.min(Math.max(0, availableWidth), maxHeight * ratio);
  return { width, height: width / ratio };
}
