import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";
import { useAuth } from "./useAuth";

// Wraps the app-shell route in router.tsx, so every in-app page (including ones added later)
// is login-only. Logged-out visitors go to /login?next=<where they were headed>.
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  // Wait for the saved session, so signed-in users aren't bounced to login on reload.
  if (loading) return null;

  if (!user) {
    const next = location.pathname + location.search + location.hash;
    return <Navigate to={`/login?${new URLSearchParams({ next })}`} replace />;
  }

  return children;
}
