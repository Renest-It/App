import type { ReactNode } from "react";
import { Navigate } from "react-router";
import { useAuth } from "./useAuth";

// Wraps pages only signed-out visitors should see (/login, /signup).
export function GuestOnly({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();

  // Render nothing until the saved session has been read. Reading it is local and near
  // instant, so this avoids flashing the form at a signed-in user without a spinner flicker.
  if (loading) return null;

  // replace: the back button shouldn't bounce the user back to the form.
  if (user) return <Navigate to="/" replace />;

  return children;
}
