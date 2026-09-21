// Helps mirror the backend schema (see backend model: T0.8,
// and the actual response shapes in backend schema: T0.9).

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
  created_at: string;
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
  status: "active" | "sold";
  created_at: string;
}
