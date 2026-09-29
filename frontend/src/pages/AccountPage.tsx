import { Button } from "../components/Button";
import { useLogout } from "../auth/useLogout";

// Placeholder until the real profile page. Log Out moves to the Settings page
// (Figma desktop-settings 46:4 / mobile-settings 46:83) once that's built.
export function AccountPage() {
  const logout = useLogout();

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="font-display text-2xl font-bold text-text">Account</h1>
        <p className="text-body text-text-muted">Your profile is coming soon.</p>
      </div>
      <div className="w-full lg:max-w-xs">
        <Button variant="danger" onClick={logout}>
          Log Out
        </Button>
      </div>
    </div>
  );
}
