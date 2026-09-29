import type { AuthError, Session, User } from "@supabase/supabase-js";
import { createContext } from "react";
import type { CurrentUser } from "../api/types";

export type AuthResult = { error: AuthError | null };

export type AuthContextValue = {
  session: Session | null;
  user: User | null;
  // True until the saved session has been read on page load. Pages should wait for this
  // before deciding the user is logged out, or they'll flash the logged-out view.
  loading: boolean;
  // The signed-in user as the backend stored them (from GET /me), or null. Loaded once per
  // sign-in / page load; currentUserLoading is true until it arrives.
  currentUser: CurrentUser | null;
  currentUserLoading: boolean;
  signUp: (email: string, password: string, displayName: string) => Promise<AuthResult>;
  signIn: (email: string, password: string) => Promise<AuthResult>;
  signOut: () => Promise<AuthResult>;
  // Re-sends the verification email for an account that hasn't been confirmed yet.
  resend: (email: string) => Promise<AuthResult>;
};

export const AuthContext = createContext<AuthContextValue | null>(null);
