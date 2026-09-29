import { Button } from "../components/Button";
import { useAuth } from "../auth/useAuth";
import { useLogout } from "../auth/useLogout";

// Placeholder until the real profile page. Log Out moves to the Settings page
// (Figma desktop-settings 46:4 / mobile-settings 46:83) once that's built.
export function AccountPage() {
  const { currentUser, currentUserLoading } = useAuth();
  const logout = useLogout();

  return (
    <div className="flex flex-col gap-6">
      <h1 className="font-display text-2xl font-bold text-text">Account</h1>

      {currentUserLoading ? (
        <div aria-hidden className="flex animate-pulse flex-col gap-2">
          <div className="h-6 w-40 rounded-sm bg-border" />
          <div className="h-4 w-56 rounded-sm bg-border" />
        </div>
      ) : currentUser ? (
        <div className="flex min-w-0 flex-col gap-1">
          <p className="font-display text-heading font-bold break-words text-text">
            {currentUser.display_name ?? currentUser.email.split("@")[0]}
          </p>
          <p className="text-body break-all text-text-muted">{currentUser.email}</p>
        </div>
      ) : (
        <p className="text-body text-text-muted">We couldn't load your profile right now.</p>
      )}

      <div className="w-full lg:max-w-xs">
        <Button variant="danger" onClick={logout}>
          Log Out
        </Button>
      </div>
    </div>
  );
}
