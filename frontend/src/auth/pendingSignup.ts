// Remembers who just signed up, so /check-email and the expired-link page still know the
// address (and the resend cooldown) after a reload. Cleared once the user is signed in.

const KEY = "renest:pendingSignup";

// Supabase won't send another verification email to the same address for ~60s.
export const RESEND_COOLDOWN_MS = 60_000;

export type PendingSignup = { email: string; resendAvailableAt: number };

export function getPendingSignup(): PendingSignup | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<PendingSignup>;
    if (typeof parsed.email !== "string" || typeof parsed.resendAvailableAt !== "number") {
      return null;
    }
    return { email: parsed.email, resendAvailableAt: parsed.resendAvailableAt };
  } catch {
    // Storage blocked (e.g. some private-browsing modes) or corrupted: behave as if empty.
    return null;
  }
}

// Saves the address and starts a fresh cooldown. Returns what was saved.
export function startPendingSignup(email: string): PendingSignup {
  const pending = { email, resendAvailableAt: Date.now() + RESEND_COOLDOWN_MS };
  try {
    localStorage.setItem(KEY, JSON.stringify(pending));
  } catch {
    // Not fatal: the pages fall back to router state for this visit.
  }
  return pending;
}

export function clearPendingSignup() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // Nothing to clean up if storage is unavailable.
  }
}
