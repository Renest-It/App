// Client-side checks for the create-listing form. These mirror the backend's rules exactly
// (docs/api/listings.md → Validation rules) so users rarely see the backend's own 422s.
// If either side changes, change both — the contract doc is the source of truth.

export const TITLE_MIN = 3;
export const TITLE_MAX = 80;
export const DESCRIPTION_MAX = 2000;
export const PRICE_MAX_CENTS = 1_000_000; // $10,000
export const MAX_PHOTOS = 6;

export type FieldErrors = {
  title?: string;
  price?: string;
  category?: string;
  photos?: string;
};

// Dollars-as-typed ("45", "12.50", "") → cents, or null if it isn't a valid non-negative amount.
export function parsePriceCents(value: string): number | null {
  const trimmed = value.trim();
  if (trimmed === "" || !/^\d+(\.\d{1,2})?$/.test(trimmed)) return null;
  return Math.round(Number(trimmed) * 100);
}

export function validateTitle(title: string): string | undefined {
  const length = title.trim().length;
  if (length === 0) return "Add a title so buyers know what this is.";
  if (length < TITLE_MIN) return `Title must be at least ${TITLE_MIN} characters.`;
  if (length > TITLE_MAX) return `Title must be ${TITLE_MAX} characters or fewer.`;
  return undefined;
}

export function validatePrice(rawValue: string): string | undefined {
  const cents = parsePriceCents(rawValue);
  if (cents === null) return "Enter a price, or 0 for a free item.";
  if (cents > PRICE_MAX_CENTS) return "Enter a price under $10,000, or 0 for a free item.";
  return undefined;
}

export function validateCategory(categoryId: string): string | undefined {
  return categoryId === "" ? "Choose a category." : undefined;
}

export function validatePhotos(photoCount: number): string | undefined {
  return photoCount === 0 ? "Add at least one photo." : undefined;
}

export function validateListingForm(fields: {
  title: string;
  price: string;
  categoryId: string;
  photoCount: number;
}): FieldErrors {
  const errors: FieldErrors = {};
  const title = validateTitle(fields.title);
  const price = validatePrice(fields.price);
  const category = validateCategory(fields.categoryId);
  const photos = validatePhotos(fields.photoCount);
  if (title) errors.title = title;
  if (price) errors.price = price;
  if (category) errors.category = category;
  if (photos) errors.photos = photos;
  return errors;
}
