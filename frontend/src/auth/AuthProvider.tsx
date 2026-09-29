import type { Session } from "@supabase/supabase-js";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { getMe } from "../api/client";
import type { CurrentUser } from "../api/types";
import { supabase } from "../lib/supabase";
import { AuthContext, type AuthContextValue } from "./AuthContext";
import { clearPendingSignup } from "./pendingSignup";

// Where verification links land: /auth/confirm on whichever site the user is on (localhost,
// a Vercel preview, or production). The origin must be on Supabase's redirect allow-list,
// whose patterns end in "/**" — so the URL must have a path after the host to match.
function confirmRedirectUrl() {
  return `${window.location.origin}/auth/confirm`;
}

// The actions don't update state themselves — Supabase fires an auth event afterward,
// and the listener below is the single place that writes the session.
async function signUp(email: string, password: string, displayName: string) {
  const { error } = await supabase.auth.signUp({
    email,
    password,
    options: {
      emailRedirectTo: confirmRedirectUrl(),
      // Stored in user.user_metadata.display_name.
      data: { display_name: displayName },
    },
  });
  return { error };
}

async function signIn(email: string, password: string) {
  const { error } = await supabase.auth.signInWithPassword({ email, password });
  return { error };
}

async function signOut() {
  const { error } = await supabase.auth.signOut();
  return { error };
}

async function resend(email: string) {
  const { error } = await supabase.auth.resend({
    type: "signup",
    email,
    options: { emailRedirectTo: confirmRedirectUrl() },
  });
  return { error };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // The first event is INITIAL_SESSION, fired once the saved session has been read, so
    // that's when loading ends. Later events cover sign-in, sign-out, token refresh, and
    // changes made in other tabs.
    // Keep this callback synchronous: awaiting other supabase.auth calls in here can deadlock.
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, newSession) => {
      setSession(newSession);
      setLoading(false);
      // Once someone is signed in, the "who just signed up" note has served its purpose.
      if (newSession) clearPendingSignup();
      // The saved session is read from localStorage without asking Supabase, so it outlives an
      // account that was deleted (or banned) server-side. Check once per page load; if the
      // account is gone, clear the local session so the user isn't stuck "signed in".
      // setTimeout: calling supabase.auth inside this callback can deadlock (see above).
      if (event === "INITIAL_SESSION" && newSession) {
        setTimeout(async () => {
          const { error } = await supabase.auth.getUser();
          if (error && (error.status === 401 || error.status === 403 || error.status === 404)) {
            await supabase.auth.signOut({ scope: "local" });
          }
        }, 0);
      }
    });

    return () => subscription.unsubscribe();
  }, []);

  // Load the backend's view of the user (GET /me) whenever a different user signs in. This
  // also makes sure their users row exists right after log-in. Token refreshes keep the same
  // user id, so they don't refetch. The result is stored with the id it belongs to, so a slow
  // answer for a previous user is never shown for the next one.
  const userId = session?.user.id ?? null;
  const [me, setMe] = useState<{ userId: string; user: CurrentUser | null } | null>(null);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    getMe()
      .then((user) => {
        if (!cancelled) setMe({ userId, user });
      })
      .catch(() => {
        // Auth failures are handled globally (sign-out + redirect). Anything else (e.g. a 503)
        // leaves currentUser empty; the Account page shows its placeholder.
        if (!cancelled) setMe({ userId, user: null });
      });
    return () => {
      cancelled = true;
    };
  }, [userId]);

  const currentUser = me && me.userId === userId ? me.user : null;
  const currentUserLoading = userId !== null && me?.userId !== userId;

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      user: session?.user ?? null,
      loading,
      currentUser,
      currentUserLoading,
      signUp,
      signIn,
      signOut,
      resend,
    }),
    [session, loading, currentUser, currentUserLoading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
