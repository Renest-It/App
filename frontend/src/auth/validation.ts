// Client-side checks for the auth forms. These are for user experience only — the backend
// (FastAPI) is the real enforcement of the @creighton.edu rule.

// Must match Supabase → Authentication → Sign In / Providers → Email → "Minimum password length".
// If you change it there, change it here too.
export const PASSWORD_MIN_LENGTH = 6;

const CREIGHTON_DOMAIN = "@creighton.edu";

export function normalizeEmail(value: string) {
  return value.trim().toLowerCase();
}

export function isCreightonEmail(value: string) {
  return normalizeEmail(value).endsWith(CREIGHTON_DOMAIN);
}

// True once the user has typed something like "name@domain.tld", so the Creighton check
// doesn't flash an error while they're still typing "you@cre...".
export function looksComplete(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizeEmail(value));
}
