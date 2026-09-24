import { useCallback } from "react";
import { useNavigate } from "react-router";
import { useAuth } from "./useAuth";

// Log-out action for the Account tab (E1.3.5): ends the session and goes to /login.
export function useLogout() {
  const { signOut } = useAuth();
  const navigate = useNavigate();

  return useCallback(async () => {
    const { error } = await signOut();
    navigate("/login", { replace: true });
    return { error };
  }, [signOut, navigate]);
}
