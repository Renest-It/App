// Resizes and re-encodes a photo before it leaves the browser (E2.5, see ADR 0009): longest
// side capped at 1600px, re-encoded as JPEG, stepped down in quality until it's comfortably
// under the storage bucket's 5MB limit. Re-encoding through canvas also strips all metadata,
// including GPS — that's the point, not a side effect.
//
// Orientation: evergreen browsers decode EXIF-rotated JPEGs already upright by default (the
// CSS Images spec's `image-orientation: from-image` default, which createImageBitmap/<img>/
// canvas drawImage all follow) — confirmed here on Chromium: `createImageBitmap(file, {
// imageOrientation: "none" })` is NOT honored and returns the same already-rotated bitmap as
// the default. So this does NOT also apply its own rotation from the EXIF tag — doing that on
// top of the browser's own would double-rotate the photo. It just resizes/encodes whatever the
// browser handed back, which is already upright. Verify this still holds with a real portrait
// iPhone photo before shipping, in case Safari ever disagrees.

const MAX_DIMENSION = 1600;
const JPEG_QUALITY_STEPS = [0.8, 0.6, 0.45, 0.3];
const TARGET_MAX_BYTES = 4 * 1024 * 1024; // safety margin under the bucket's 5MB cap

export async function processImage(file: File): Promise<File> {
  const source = await decodeImage(file);
  try {
    const { width: sourceWidth, height: sourceHeight } = sourceDimensions(source);
    const { width, height } = computeTargetDimensions(sourceWidth, sourceHeight, MAX_DIMENSION);

    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Could not process image");
    ctx.drawImage(source, 0, 0, width, height);

    const blob = await encodeUnderLimit((quality) => canvasToBlob(canvas, quality));
    return new File([blob], jpegFileName(file.name), { type: "image/jpeg" });
  } finally {
    if ("close" in source) source.close();
  }
}

// Thrown when neither decode path can read the file at all — in practice, HEIC photos on a
// browser with no HEIC decoder (confirmed: Chrome has none; Safari decodes HEIC natively via
// macOS/iOS's system codec). Distinct from a network/upload failure so the caller can show a
// message that doesn't tell the user to just retry — retrying won't help an unsupported format.
export class UnsupportedImageError extends Error {
  constructor() {
    super("This photo's format isn't supported by your browser.");
    this.name = "UnsupportedImageError";
  }
}

async function decodeImage(file: File): Promise<ImageBitmap | HTMLImageElement> {
  if (typeof createImageBitmap === "function") {
    try {
      return await createImageBitmap(file);
    } catch {
      // fall through to the <img> fallback below
    }
  }
  try {
    return await loadImageElement(file);
  } catch {
    throw new UnsupportedImageError();
  }
}

function loadImageElement(file: File): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve(img);
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Could not read image file"));
    };
    img.src = url;
  });
}

function sourceDimensions(source: ImageBitmap | HTMLImageElement) {
  return "naturalWidth" in source
    ? { width: source.naturalWidth, height: source.naturalHeight }
    : { width: source.width, height: source.height };
}

export function computeTargetDimensions(
  sourceWidth: number,
  sourceHeight: number,
  maxDimension: number,
) {
  const scale = Math.min(1, maxDimension / Math.max(sourceWidth, sourceHeight));
  return { width: Math.round(sourceWidth * scale), height: Math.round(sourceHeight * scale) };
}

export async function encodeUnderLimit(
  encode: (quality: number) => Promise<Blob>,
  qualities: number[] = JPEG_QUALITY_STEPS,
  maxBytes: number = TARGET_MAX_BYTES,
): Promise<Blob> {
  let lastBlob: Blob | null = null;
  for (const quality of qualities) {
    const blob = await encode(quality);
    lastBlob = blob;
    if (blob.size <= maxBytes) return blob;
  }
  // Exhausted every step — hand back the smallest we managed rather than failing the upload.
  return lastBlob!;
}

function canvasToBlob(canvas: HTMLCanvasElement, quality: number): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("Could not encode image"))),
      "image/jpeg",
      quality,
    );
  });
}

function jpegFileName(name: string): string {
  return `${name.replace(/\.[^.]+$/, "")}.jpg`;
}
