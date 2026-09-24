import type { Session } from "@supabase/supabase-js";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { supabase } from "../lib/supabase";
import { AuthContext, type AuthContextValue } from "./AuthContext";

// The actions don't update state themselves — Supabase fires an auth event afterward,
// and the listener below is the single place that writes the session.
async function signUp(email: string, password: string) {
  const { error } = await supabase.auth.signUp({
    email,
    password,
    // Send the verification link back to whichever site the user signed up from
    // (localhost, a Vercel preview, or production). Must be on Supabase's redirect allow-list.
    options: { emailRedirectTo: window.location.origin },
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
    } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession);
      setLoading(false);
    });

    return () => subscription.unsubscribe();
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ session, user: session?.user ?? null, loading, signUp, signIn, signOut }),
    [session, loading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
