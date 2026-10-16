// Client-side upload checks. The backend enforces the same limits (and checks file contents).

export const MAX_FILES = 3;
export const MAX_TEXT_CHARS = 20_000;
export const MAX_PDF_BYTES = 10 * 1024 * 1024;
export const MAX_IMAGE_BYTES = 5 * 1024 * 1024;

const TYPES: Record<string, 'pdf' | 'image'> = {
  'application/pdf': 'pdf',
  'image/png': 'image',
  'image/jpeg': 'image',
  'image/webp': 'image',
};
const EXTENSIONS: Record<string, 'pdf' | 'image'> = { pdf: 'pdf', png: 'image', jpg: 'image', jpeg: 'image', webp: 'image' };

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function fileKind(file: { name: string; type: string }): 'pdf' | 'image' | null {
  const ext = file.name.split('.').pop()?.toLowerCase() ?? '';
  return TYPES[file.type] ?? EXTENSIONS[ext] ?? null;
}

/** Returns a user-facing problem, or null when the file can be added. */
export function validateFile(file: { name: string; type: string; size: number }, existing: { name: string; size: number }[]): string | null {
  const kind = fileKind(file);
  if (!kind) return `'${file.name}' is not supported. Upload a PDF, PNG, JPG or WebP file.`;
  if (file.size === 0) return `'${file.name}' is empty.`;
  if (kind === 'pdf' && file.size > MAX_PDF_BYTES) return `'${file.name}' is larger than 10 MB.`;
  if (kind === 'image' && file.size > MAX_IMAGE_BYTES) return `'${file.name}' is larger than 5 MB.`;
  if (existing.some((f) => f.name === file.name && f.size === file.size)) return `'${file.name}' is already added.`;
  if (existing.length >= MAX_FILES) return `You can upload up to ${MAX_FILES} files.`;
  return null;
}
