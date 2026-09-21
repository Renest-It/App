// Mirrors the backend schema exactly (see backend/app/models/{listing,category}.py, T0.8).
// price_cents stays an integer here — never convert to dollars in the type layer.
// Use formatPriceCents() from ./format for display.

export interface Category {
  id: number;
  name: string;
  slug: string;
}

export interface Listing {
  id: string;
  seller_id: string;
  title: string;
  description: string | null;
  price_cents: number;
  category_id: number | null;
  status: "active" | "sold";
  created_at: string;
  updated_at: string | null;
}

export interface ListingCreate {
  title: string;
  description?: string | null;
  price_cents: number;
  category_id: number;
}
