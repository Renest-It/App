// Mock ReNest API for E2, following docs/api/listings.md. Turn it on with VITE_USE_MOCKS=true
// in frontend/.env. When the real endpoints land (E2.2/E2.3), turn the mocks off: no
// component changes are needed.
//
// State lives in memory and resets on page reload. Routes not handled here (e.g. /me) go to
// the real API as usual.

import { http, HttpResponse } from "msw";
import type {
  Category,
  ImageContentType,
  ImageUploadUrl,
  Listing,
  ListingDetail,
  ListingImage,
  ListingStatus,
} from "../api/types";

const API = import.meta.env.VITE_API_BASE_URL;
// Fake stand-in for the Supabase Storage signed-upload endpoint.
const STORAGE = "https://mock-storage.renest.test";

const MAX_FILE_BYTES = 5 * 1024 * 1024;
const MAX_POSITION = 5;
const EXTENSIONS: Record<ImageContentType, string> = {
  "image/jpeg": "jpg",
  "image/png": "png",
  "image/webp": "webp",
};

const CATEGORIES: Category[] = [
  { id: 1, name: "Furniture", slug: "furniture" },
  { id: 2, name: "Electronics", slug: "electronics" },
  { id: 3, name: "Textbooks", slug: "textbooks" },
  { id: 4, name: "Clothing", slug: "clothing" },
  { id: 5, name: "Kitchen", slug: "kitchen" },
  { id: 6, name: "Decor", slug: "decor" },
  { id: 7, name: "Other", slug: "other" },
];

interface MockUser {
  id: string;
  display_name: string | null;
}

interface MockImage extends ListingImage {
  storage_path: string;
}

interface MockListing {
  id: string;
  title: string;
  description: string | null;
  price_cents: number;
  category_id: number;
  status: ListingStatus;
  seller: MockUser;
  images: MockImage[];
  created_at: string;
}

// A grey placeholder, so seeded listings have a "photo" without any network request.
const PLACEHOLDER_PHOTO =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600"><rect width="100%" height="100%" fill="#d6d3d1"/></svg>',
  );

const OTHER_SELLER: MockUser = { id: "00000000-0000-4000-8000-000000000002", display_name: "Sam" };

const listings = new Map<string, MockListing>();
// Files "uploaded" to the fake storage, by storage path → object URL for display.
const uploads = new Map<string, string>();

function seed(listing: Omit<MockListing, "images">, withPhoto: boolean) {
  const images: MockImage[] = withPhoto
    ? [
        {
          id: crypto.randomUUID(),
          position: 0,
          url: PLACEHOLDER_PHOTO,
          storage_path: `listings/${listing.id}/seed.png`,
        },
      ]
    : [];
  listings.set(listing.id, { ...listing, images });
}

seed(
  {
    id: "00000000-0000-4000-8000-00000000a001",
    title: "Mini fridge",
    description: "Fits under a dorm desk. Pick up at Kiewit.",
    price_cents: 4000,
    category_id: 2,
    status: "active",
    seller: OTHER_SELLER,
    created_at: "2026-09-28T15:00:00Z",
  },
  true,
);
seed(
  {
    id: "00000000-0000-4000-8000-00000000a002",
    title: "Intro to Psychology textbook",
    description: null,
    price_cents: 0,
    category_id: 3,
    status: "active",
    seller: OTHER_SELLER,
    created_at: "2026-09-27T12:00:00Z",
  },
  false, // cover_image_url: null, like listings from before E2
);
// Someone else's draft: every request about it must get 404.
seed(
  {
    id: "00000000-0000-4000-8000-00000000d001",
    title: "Sam's unfinished draft",
    description: null,
    price_cents: 1000,
    category_id: 1,
    status: "draft",
    seller: OTHER_SELLER,
    created_at: "2026-09-29T09:00:00Z",
  },
  false,
);

// --- helpers -------------------------------------------------------------------------------

function error(status: number, code: string, message: string) {
  return HttpResponse.json({ code, message }, { status });
}

// FastAPI's default validation error shape, for body fields that fail the validation rules.
function validationError(field: string, msg: string) {
  return HttpResponse.json(
    { detail: [{ type: "value_error", loc: ["body", field], msg }] },
    { status: 422 },
  );
}

// The mock trusts the token without verifying it: it only reads who is asking, so "your
// listing" vs "someone else's" behaves like the real API.
function currentUser(request: Request): MockUser {
  const token = request.headers.get("Authorization")?.replace(/^Bearer /, "");
  try {
    const payload = JSON.parse(atob(token!.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return {
      id: payload.sub,
      display_name: payload.user_metadata?.display_name ?? payload.email?.split("@")[0] ?? null,
    };
  } catch {
    return { id: "00000000-0000-4000-8000-000000000001", display_name: "You" };
  }
}

function category(id: number): Category {
  return CATEGORIES.find((c) => c.id === id)!;
}

function publicImage({ id, position, url }: MockImage): ListingImage {
  return { id, position, url };
}

function toDetail(listing: MockListing): ListingDetail {
  return {
    id: listing.id,
    title: listing.title,
    description: listing.description,
    price_cents: listing.price_cents,
    status: listing.status,
    category: category(listing.category_id),
    seller: { id: listing.seller.id, display_name: listing.seller.display_name },
    images: [...listing.images].sort((a, b) => a.position - b.position).map(publicImage),
    created_at: listing.created_at,
  };
}

function toListItem(listing: MockListing): Listing {
  return {
    id: listing.id,
    title: listing.title,
    description: listing.description,
    price_cents: listing.price_cents,
    category: category(listing.category_id),
    cover_image_url: listing.images.find((i) => i.position === 0)?.url ?? null,
    created_at: listing.created_at,
  };
}

type Lookup = { listing: MockListing } | { response: Response };

// Someone else's draft is reported exactly like a missing listing (404).
function findVisible(request: Request, id: string): Lookup {
  const listing = listings.get(id);
  if (!listing || (listing.status === "draft" && listing.seller.id !== currentUser(request).id)) {
    return { response: error(404, "listing_not_found", "Listing not found.") };
  }
  return { listing };
}

// For the image and publish endpoints: must be visible AND yours.
function findOwned(request: Request, id: string): Lookup {
  const found = findVisible(request, id);
  if ("response" in found) return found;
  if (found.listing.seller.id !== currentUser(request).id) {
    return { response: error(403, "not_owner", "You can't change someone else's listing.") };
  }
  return found;
}

// --- handlers ------------------------------------------------------------------------------

export const handlers = [
  http.get(`${API}/categories`, () => HttpResponse.json(CATEGORIES)),

  http.get(`${API}/listings`, () =>
    HttpResponse.json(
      [...listings.values()]
        .filter((l) => l.status === "active")
        .sort((a, b) => b.created_at.localeCompare(a.created_at))
        .map(toListItem),
    ),
  ),

  http.post(`${API}/listings`, async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    const title = typeof body.title === "string" ? body.title.trim() : "";
    const description =
      typeof body.description === "string" ? body.description.trim() || null : null;
    const price = body.price_cents;

    if (title.length < 3 || title.length > 80) {
      return validationError("title", "Title must be 3–80 characters");
    }
    if (description && description.length > 2000) {
      return validationError("description", "Description must be at most 2,000 characters");
    }
    if (typeof price !== "number" || !Number.isInteger(price) || price < 0 || price > 1_000_000) {
      return validationError("price_cents", "Price must be between $0 and $10,000");
    }
    if (typeof body.category_id !== "number") {
      return validationError("category_id", "Category is required");
    }
    if (!CATEGORIES.some((c) => c.id === body.category_id)) {
      return error(422, "unknown_category", "That category doesn't exist.");
    }

    const listing: MockListing = {
      id: crypto.randomUUID(),
      title,
      description,
      price_cents: price,
      category_id: body.category_id,
      status: "draft",
      seller: currentUser(request),
      images: [],
      created_at: new Date().toISOString(),
    };
    listings.set(listing.id, listing);

    return HttpResponse.json(
      {
        id: listing.id,
        title: listing.title,
        description: listing.description,
        price_cents: listing.price_cents,
        category_id: listing.category_id,
        status: listing.status,
        created_at: listing.created_at,
      },
      { status: 201 },
    );
  }),

  http.get(`${API}/listings/:id`, ({ request, params }) => {
    const found = findVisible(request, params.id as string);
    if ("response" in found) return found.response;
    return HttpResponse.json(toDetail(found.listing));
  }),

  http.post(`${API}/listings/:id/images/upload-url`, async ({ request, params }) => {
    const found = findOwned(request, params.id as string);
    if ("response" in found) return found.response;
    if (found.listing.status !== "draft") {
      return error(409, "listing_not_draft", "Photos can only be added before publishing.");
    }

    const { content_type } = (await request.json()) as { content_type?: string };
    const ext = EXTENSIONS[content_type as ImageContentType];
    if (!ext) {
      return error(422, "unsupported_content_type", "Photos must be JPEG, PNG, or WebP.");
    }

    const storagePath = `listings/${found.listing.id}/${crypto.randomUUID()}.${ext}`;
    const body: ImageUploadUrl = {
      upload_url: `${STORAGE}/upload/${storagePath}?token=mock`,
      storage_path: storagePath,
      expires_in: 7200,
    };
    return HttpResponse.json(body);
  }),

  // The fake storage upload. The real bucket enforces the same type and size limits.
  http.put(`${STORAGE}/upload/*`, async ({ request }) => {
    const path = decodeURIComponent(new URL(request.url).pathname.replace(/^\/upload\//, ""));
    const type = request.headers.get("Content-Type") ?? "";
    if (!(type in EXTENSIONS)) {
      return HttpResponse.json({ error: "invalid_mime_type" }, { status: 415 });
    }
    const file = await request.blob();
    if (file.size > MAX_FILE_BYTES) {
      return HttpResponse.json({ error: "Payload too large" }, { status: 413 });
    }
    uploads.set(path, URL.createObjectURL(new Blob([file], { type })));
    return HttpResponse.json({ Key: `listing-photos/${path}` });
  }),

  http.post(`${API}/listings/:id/images`, async ({ request, params }) => {
    const found = findOwned(request, params.id as string);
    if ("response" in found) return found.response;
    const { listing } = found;
    if (listing.status !== "draft") {
      return error(409, "listing_not_draft", "Photos can only be added before publishing.");
    }

    const { storage_path, position } = (await request.json()) as {
      storage_path?: string;
      position?: number;
    };
    if (
      typeof position !== "number" ||
      !Number.isInteger(position) ||
      position < 0 ||
      position > MAX_POSITION
    ) {
      return validationError("position", "Position must be 0–5");
    }
    if (typeof storage_path !== "string" || !storage_path.startsWith(`listings/${listing.id}/`)) {
      return error(422, "invalid_storage_path", "That photo doesn't belong to this listing.");
    }

    const existing = listing.images.find((i) => i.position === position);
    if (existing) {
      // Identical retry: return the image already recorded.
      if (existing.storage_path === storage_path) {
        return HttpResponse.json(publicImage(existing), { status: 200 });
      }
      return error(409, "position_taken", "Another photo already has that position.");
    }

    const image: MockImage = {
      id: crypto.randomUUID(),
      position,
      storage_path,
      url: uploads.get(storage_path) ?? PLACEHOLDER_PHOTO,
    };
    listing.images.push(image);
    return HttpResponse.json(publicImage(image), { status: 201 });
  }),

  http.post(`${API}/listings/:id/publish`, ({ request, params }) => {
    const found = findOwned(request, params.id as string);
    if ("response" in found) return found.response;
    const { listing } = found;
    if (listing.status !== "draft") {
      return error(409, "already_published", "This listing is already published.");
    }
    if (listing.images.length === 0) {
      return error(422, "no_images", "Add at least one photo before publishing.");
    }
    listing.status = "active";
    return HttpResponse.json(toDetail(listing));
  }),
];
