import type { AuthFailureReason } from "../api/client";
import { supabase } from "../lib/supabase";
import { safeNext } from "./safeNext";

type Navigator = { navigate: (to: string, opts?: { replace?: boolean }) => unknown };

let handling = false;

// Called (via setAuthFailureHandler in main.tsx) when the API rejects the current session:
// 401 (expired/invalid), 403 wrong_domain / email_not_confirmed, or 409 email_conflict.
// Signs out in this browser and sends the user to log in with a reason banner.
export async function handleAuthFailure(reason: AuthFailureReason, router: Navigator) {
  // Several requests can fail at once; redirect only once.
  if (handling) return;
  handling = true;
  try {
    const here = window.location.pathname + window.location.search + window.location.hash;
    const next = safeNext(here);

    // "local": just clear this browser's session. The server already rejected the token.
    await supabase.auth.signOut({ scope: "local" });

    const params = new URLSearchParams({ reason });
    if (next && next !== "/") params.set("next", next);
    await router.navigate(`/login?${params}`, { replace: true });
  } finally {
    handling = false;
  }
}
