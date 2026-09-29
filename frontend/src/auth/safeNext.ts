// Validates a `next` redirect target (e.g. /login?next=/sell) so it can only point inside the
// app. Without this, anyone could craft a login link that sends users to another site after
// they sign in (an open redirect).

// A placeholder origin to resolve against: if the result has any other origin, `next` tried
// to leave the app. Using the browser's own URL parser catches tricks a regex would miss.
const ORIGIN_PROBE = "https://renest.invalid";

// Sending someone "back" to an auth page after logging in makes no sense.
const AUTH_PATHS = new Set(["/login", "/signup", "/check-email", "/auth/confirm"]);

export function safeNext(raw: string | null | undefined): string | null {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//") || raw.includes("\\")) return null;

  let url: URL;
  try {
    url = new URL(raw, ORIGIN_PROBE);
  } catch {
    return null;
  }
  if (url.origin !== ORIGIN_PROBE) return null;
  if (AUTH_PATHS.has(url.pathname)) return null;

  const path = url.pathname + url.search + url.hash;
  // Dot segments can normalize into a protocol-relative URL: "/..//evil.com" → "//evil.com",
  // which a browser treats as another site. Check the *result*, not just the input.
  if (path.startsWith("//")) return null;
  return path;
}
