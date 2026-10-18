// Helps mirror the backend schema (see backend model: T0.8,
// and the actual response shapes in backend schema: T0.9).
// E2's and E3's listing shapes are defined in docs/api/listings.md.

export type ListingStatus = "draft" | "active" | "sold";

export interface Category {
  id: number;
  name: string;
  slug: string;
}

// What GET /listings actually returns: category is a nested object.
export interface Listing {
  id: string;
  title: string;
  description: string | null;
  price_cents: number;
  category: Category;
  // The photo at position 0, or null if the listing has none (e.g. listings from before E2).
  cover_image_url: string | null;
  created_at: string;
}

// What GET /listings/mine returns: the feed's shape, plus status (it includes drafts and sold).
export interface MyListing extends Listing {
  status: ListingStatus;
}

export interface ListingCreate {
  title: string;
  description?: string | null;
  price_cents: number;
  category_id: number;
}

// What POST /listings actually returns: category_id is flat, not nested.
// Different shape from Listing on purpose
// This matches the real backend response.
export interface CreatedListing {
  id: string;
  title: string;
  description: string | null;
  price_cents: number;
  category_id: number | null;
  status: ListingStatus;
  created_at: string;
}

// What GET /me returns: the signed-in user as the backend stored them.
export interface CurrentUser {
  id: string;
  email: string;
  display_name: string | null;
  created_at: string;
}

// One photo of a listing. Position 0 is the cover.
export interface ListingImage {
  id: string;
  position: number;
  url: string;
}

// The seller as shown on a listing. Never includes email (see docs/api/listings.md).
export interface Seller {
  id: string;
  display_name: string | null;
}

// PATCH /listings/{id}: send only the fields that changed. description: null clears it.
export interface ListingUpdate {
  title?: string;
  description?: string | null;
  price_cents?: number;
  category_id?: number;
}

// What GET /listings/{id}, PATCH /listings/{id}, and POST /listings/{id}/publish, /sold, and
// /unsold return.
export interface ListingDetail {
  id: string;
  title: string;
  description: string | null;
  price_cents: number;
  status: ListingStatus;
  category: Category;
  seller: Seller;
  images: ListingImage[]; // sorted by position
  created_at: string;
}

export type ImageContentType = "image/jpeg" | "image/png" | "image/webp";

// What POST /listings/{id}/images/upload-url returns. PUT the file to upload_url.
export interface ImageUploadUrl {
  upload_url: string;
  storage_path: string;
  expires_in: number; // seconds
}

export interface ListingImageCreate {
  storage_path: string;
  position: number;
}
