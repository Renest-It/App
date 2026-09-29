import { supabase } from "../lib/supabase";
import type { Category, CreatedListing, CurrentUser, Listing, ListingCreate } from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL;

if (!BASE_URL) {
  throw new Error(
    "VITE_API_BASE_URL is not set. Copy frontend/.env.example to frontend/.env and set it.",
  );
}

// Thrown when the server responds, but with an error status.
export class ApiError extends Error {
  status: number;
  // The backend's machine-readable reason, when it sends one
  // (e.g. "invalid_token", "wrong_domain", "email_conflict", "auth_unavailable").
  code?: string;

  constructor(status: number, message: string, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
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

// Why the API refused the current session. The app signs the user out and explains why.
export type AuthFailureReason =
  "expired" | "wrong_domain" | "email_not_confirmed" | "email_conflict";

let onAuthFailure: ((reason: AuthFailureReason) => void) | null = null;

// Registered once in main.tsx (this module can't navigate by itself).
export function setAuthFailureHandler(handler: (reason: AuthFailureReason) => void) {
  onAuthFailure = handler;
}

function authFailureReason(error: ApiError): AuthFailureReason | null {
  if (error.status === 401) return "expired";
  if (error.status === 403 && error.code === "wrong_domain") return "wrong_domain";
  if (error.status === 403 && error.code === "email_not_confirmed") return "email_not_confirmed";
  if (error.status === 409 && error.code === "email_conflict") return "email_conflict";
  // Everything else (including 503 auth_unavailable) is a normal error, not a sign-out.
  return null;
}

// Every call to the ReNest API goes through here. It's the ONLY place that attaches the
// session token and the only place auth failures are detected, so new API functions
// (e.g. E2's) get both just by calling request().
async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  // getSession() refreshes the access token first if it's about to expire.
  const { data } = await supabase.auth.getSession();
  const headers = new Headers(init.headers);
  if (data.session) {
    headers.set("Authorization", `Bearer ${data.session.access_token}`);
  }

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, { ...init, headers });
  } catch {
    throw new NetworkError();
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const error = new ApiError(
      response.status,
      body?.message ?? body?.detail ?? response.statusText,
      body?.code,
    );
    const reason = authFailureReason(error);
    if (reason) onAuthFailure?.(reason);
    throw error;
  }

  return response.json();
}

export const getListings = () => request<Listing[]>("/listings");

export const getCategories = () => request<Category[]>("/categories");

export const createListing = (data: ListingCreate) =>
  request<CreatedListing>("/listings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });

export const getMe = () => request<CurrentUser>("/me");
