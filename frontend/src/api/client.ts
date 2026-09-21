import type { Category, CreatedListing, Listing, ListingCreate } from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL;

if (!BASE_URL) {
  throw new Error(
    "VITE_API_BASE_URL is not set. Copy frontend/.env.example to frontend/.env and set it.",
  );
}

// Thrown when the server responds, but with an error status.
export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// Thrown when the request never reached the server at all (offline, failure..)
// This is different from ApiError, where the server DID respond, just with an error.
export class NetworkError extends Error {
  constructor() {
    super("Could not reach the server. Check your connection.");
    this.name = "NetworkError";
  }
}

export async function getListings(): Promise<Listing[]> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}/listings`);
  } catch {
    throw new NetworkError();
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(response.status, body?.detail ?? response.statusText);
  }

  return response.json();
}

export async function getCategories(): Promise<Category[]> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}/categories`);
  } catch {
    throw new NetworkError();
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(response.status, body?.detail ?? response.statusText);
  }

  return response.json();
}

export async function createListing(data: ListingCreate): Promise<CreatedListing> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}/listings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
  } catch {
    throw new NetworkError();
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(response.status, body?.detail ?? response.statusText);
  }

  return response.json();
}
