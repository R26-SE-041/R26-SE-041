export const MAX_THREED_IMAGE_BYTES = 10 * 1024 * 1024;
export const THREED_IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp"];

export function validateThreeDImage(size: number | undefined, mimeType: string | undefined, name: string): void {
  const supported = mimeType ? THREED_IMAGE_TYPES.includes(mimeType.toLowerCase()) : /\.(png|jpe?g|webp)$/i.test(name);
  if (!supported) throw new Error("Choose a PNG, JPEG, or WebP image.");
  if (!size) throw new Error("This image is empty or its size could not be read. Choose another image.");
  if (size > MAX_THREED_IMAGE_BYTES) throw new Error("Choose an image smaller than 10 MB.");
}
