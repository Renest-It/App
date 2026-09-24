import type { ReactNode } from "react";
import { Navigate, useSearchParams } from "react-router";
import { safeNext } from "./safeNext";
import { useAuth } from "./useAuth";

// Wraps pages only signed-out visitors should see (/login, /signup).
export function GuestOnly({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const [params] = useSearchParams();

  // Render nothing until the saved session has been read. Reading it is local and near
  // instant, so this avoids flashing the form at a signed-in user without a spinner flicker.
  if (loading) return null;

  // Signed in: go where they were headed (if it's a safe in-app path), otherwise Home.
  // replace: the back button shouldn't bounce the user back to the form.
  if (user) return <Navigate to={safeNext(params.get("next")) ?? "/"} replace />;

  return children;
}
