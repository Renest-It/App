// Mock ReNest API for E2 and E3, following docs/api/listings.md. Turn it on with
// VITE_USE_MOCKS=true in frontend/.env. When the real endpoints land (E3.2/E3.3), turn the
// mocks off: no component changes are needed.
//
// The image endpoints already follow E3.3's rule (any listing of yours that isn't sold, not
// just drafts), so the edit page (E3.4) can add photos to published listings.
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
  MyListing,
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
const LISTING_STATUSES: ListingStatus[] = ["draft", "active", "sold"];

const listings = new Map<string, MockListing>();
// Files "uploaded" to the fake storage, by storage path → object URL for display.
const uploads = new Map<string, string>();

function seed(listing: Omit<MockListing, "images">, photos: number) {
  const images: MockImage[] = Array.from({ length: photos }, (_, position) => ({
    id: crypto.randomUUID(),
    position,
    url: PLACEHOLDER_PHOTO,
    storage_path: `listings/${listing.id}/seed-${position}.png`,
  }));
  listings.set(listing.id, { ...listing, images });
}

// Every user the mock sees gets one listing of each status, so My Listings (E3.5) and the
// seller actions (E3.4) have something to work with right away.
const seededUsers = new Set<string>();
function seedOwnListings(user: MockUser) {
  if (seededUsers.has(user.id)) return;
  seededUsers.add(user.id);
  const base = { description: null, seller: user };
  seed(
    {
      ...base,
      id: crypto.randomUUID(),
      title: "Desk lamp",
      price_cents: 1500,
      category_id: 2,
      status: "active",
      created_at: "2026-09-30T18:00:00Z",
    },
    2,
  );
  seed(
    {
      ...base,
      id: crypto.randomUUID(),
      title: "Bookshelf (unfinished draft)",
      price_cents: 2500,
      category_id: 1,
      status: "draft",
      created_at: "2026-09-29T20:00:00Z",
    },
    0,
  );
  seed(
    {
      ...base,
      id: crypto.randomUUID(),
      title: "Calculus textbook",
      price_cents: 3000,
      category_id: 3,
      status: "sold",
      created_at: "2026-09-25T16:00:00Z",
    },
    1,
  );
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
  1,
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
  0, // cover_image_url: null, like listings from before E2
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
  0,
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
  const user = userFromToken(request);
  seedOwnListings(user);
  return user;
}

function userFromToken(request: Request): MockUser {
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

function toMyListing(listing: MockListing): MyListing {
  return { ...toListItem(listing), status: listing.status };
}

// The validation rules shared by POST /listings and PATCH /listings/{id}. With `partial`, a
// field that's missing is left alone instead of being an error.
type ListingFields = Partial<
  Pick<MockListing, "title" | "description" | "price_cents" | "category_id">
>;
function checkFields(
  body: Record<string, unknown>,
  partial: boolean,
): { fields: ListingFields } | { response: Response } {
  const fields: ListingFields = {};
  const has = (key: string) => !partial || key in body;

  if (has("title")) {
    const title = typeof body.title === "string" ? body.title.trim() : "";
    if (title.length < 3 || title.length > 80) {
      return { response: validationError("title", "Title must be 3–80 characters") };
    }
    fields.title = title;
  }
  if (has("description")) {
    const description =
      typeof body.description === "string" ? body.description.trim() || null : null;
    if (description && description.length > 2000) {
      return {
        response: validationError("description", "Description must be at most 2,000 characters"),
      };
    }
    fields.description = description;
  }
  if (has("price_cents")) {
    const price = body.price_cents;
    if (typeof price !== "number" || !Number.isInteger(price) || price < 0 || price > 1_000_000) {
      return { response: validationError("price_cents", "Price must be between $0 and $10,000") };
    }
    fields.price_cents = price;
  }
  if (has("category_id")) {
    if (typeof body.category_id !== "number") {
      return { response: validationError("category_id", "Category is required") };
    }
    if (!CATEGORIES.some((c) => c.id === body.category_id)) {
      return { response: error(422, "unknown_category", "That category doesn't exist.") };
    }
    fields.category_id = body.category_id;
  }
  return { fields };
}

function soldError() {
  return error(409, "listing_sold", "Sold listings can't be changed. Mark it unsold first.");
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

// For every endpoint that changes a listing: someone else's listing, whatever its status, is
// a 404 exactly like a missing one (the backend's get_owned_listing()).
function findOwned(request: Request, id: string): Lookup {
  const listing = listings.get(id);
  if (!listing || listing.seller.id !== currentUser(request).id) {
    return { response: error(404, "listing_not_found", "Listing not found.") };
  }
  return { listing };
}

// --- handlers ------------------------------------------------------------------------------

export const handlers = [
  http.get(`${API}/categories`, () => HttpResponse.json(CATEGORIES)),

  http.get(`${API}/listings`, ({ request }) => {
    currentUser(request); // so your own seeded active listing shows in the feed too
    return HttpResponse.json(
      [...listings.values()]
        .filter((l) => l.status === "active")
        .sort((a, b) => b.created_at.localeCompare(a.created_at))
        .map(toListItem),
    );
  }),

  http.post(`${API}/listings`, async ({ request }) => {
    const checked = checkFields((await request.json()) as Record<string, unknown>, false);
    if ("response" in checked) return checked.response;
    const { title, description, price_cents, category_id } = checked.fields;

    const listing: MockListing = {
      id: crypto.randomUUID(),
      title: title!,
      description: description ?? null,
      price_cents: price_cents!,
      category_id: category_id!,
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

  // Declared before /listings/:id, or "mine" would be matched as a listing ID.
  http.get(`${API}/listings/mine`, ({ request }) => {
    const status = new URL(request.url).searchParams.get("status");
    if (status !== null && !LISTING_STATUSES.includes(status as ListingStatus)) {
      return HttpResponse.json(
        {
          detail: [
            {
              type: "enum",
              loc: ["query", "status"],
              msg: "Input should be 'active', 'draft' or 'sold'",
            },
          ],
        },
        { status: 422 },
      );
    }
    const me = currentUser(request);
    return HttpResponse.json(
      [...listings.values()]
        .filter((l) => l.seller.id === me.id && (status === null || l.status === status))
        .sort((a, b) => b.created_at.localeCompare(a.created_at))
        .map(toMyListing),
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
    if (found.listing.status === "sold") return soldError();

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
    if (listing.status === "sold") return soldError();

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

  // --- E3 ----------------------------------------------------------------------------------

  http.patch(`${API}/listings/:id`, async ({ request, params }) => {
    const found = findOwned(request, params.id as string);
    if ("response" in found) return found.response;
    const { listing } = found;
    if (listing.status === "sold") return soldError();

    const checked = checkFields((await request.json()) as Record<string, unknown>, true);
    if ("response" in checked) return checked.response;
    // created_at is left alone, so an edited listing keeps its place in the feed.
    Object.assign(listing, checked.fields);
    return HttpResponse.json(toDetail(listing));
  }),

  http.delete(`${API}/listings/:id`, ({ request, params }) => {
    const found = findOwned(request, params.id as string);
    if ("response" in found) return found.response;
    listings.delete(found.listing.id);
    return new HttpResponse(null, { status: 204 });
  }),

  http.post(`${API}/listings/:id/sold`, ({ request, params }) => {
    const found = findOwned(request, params.id as string);
    if ("response" in found) return found.response;
    const { listing } = found;
    if (listing.status !== "active") {
      return error(409, "listing_not_active", "Only an active listing can be marked sold.");
    }
    listing.status = "sold";
    return HttpResponse.json(toDetail(listing));
  }),

  http.post(`${API}/listings/:id/unsold`, ({ request, params }) => {
    const found = findOwned(request, params.id as string);
    if ("response" in found) return found.response;
    const { listing } = found;
    if (listing.status !== "sold") {
      return error(409, "listing_not_sold", "This listing isn't marked sold.");
    }
    listing.status = "active";
    return HttpResponse.json(toDetail(listing));
  }),

  http.delete(`${API}/listings/:id/images/:imageId`, ({ request, params }) => {
    const found = findOwned(request, params.id as string);
    if ("response" in found) return found.response;
    const { listing } = found;
    const image = listing.images.find((i) => i.id === params.imageId);
    if (!image) return error(404, "image_not_found", "Photo not found.");
    if (listing.status === "sold") return soldError();
    if (listing.status === "active" && listing.images.length === 1) {
      return error(
        422,
        "last_photo_required",
        "A published listing needs at least one photo. Add another first.",
      );
    }
    // Close the gap so positions stay 0, 1, 2… (deleting the cover promotes the next photo).
    listing.images = listing.images
      .filter((i) => i !== image)
      .sort((a, b) => a.position - b.position)
      .map((i, position) => ({ ...i, position }));
    return new HttpResponse(null, { status: 204 });
  }),
];
