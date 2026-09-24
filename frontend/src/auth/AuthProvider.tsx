import type { Session } from "@supabase/supabase-js";
import { useEffect, useMemo, useState, type ReactNode } from "react";
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

  const value = useMemo<AuthContextValue>(
    () => ({ session, user: session?.user ?? null, loading, signUp, signIn, signOut, resend }),
    [session, loading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
