import type { AuthError, Session, User } from "@supabase/supabase-js";
import { createContext } from "react";

export type AuthResult = { error: AuthError | null };

export type AuthContextValue = {
  session: Session | null;
  user: User | null;
  // True until the saved session has been read on page load. Pages should wait for this
  // before deciding the user is logged out, or they'll flash the logged-out view.
  loading: boolean;
  signUp: (email: string, password: string) => Promise<AuthResult>;
  signIn: (email: string, password: string) => Promise<AuthResult>;
  signOut: () => Promise<AuthResult>;
};

export const AuthContext = createContext<AuthContextValue | null>(null);
