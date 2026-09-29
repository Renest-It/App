import { Mail } from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation } from "react-router";
import { Alert } from "../components/Alert";
import { AuthLayout } from "../components/AuthLayout";
import { Button, ButtonLink } from "../components/Button";
import { TextLink } from "../components/TextLink";
import { authErrorMessage } from "../auth/errorMessages";
import { getPendingSignup, startPendingSignup, type PendingSignup } from "../auth/pendingSignup";
import { useAuth } from "../auth/useAuth";

type Status = { variant: "success" | "error"; message: string } | null;

// Seconds until `availableAt`, re-rendering once a second while it's counting down.
function useSecondsUntil(availableAt: number) {
  const [now, setNow] = useState(() => Date.now());
  const secondsLeft = Math.max(0, Math.ceil((availableAt - now) / 1000));

  useEffect(() => {
    if (secondsLeft === 0) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [secondsLeft]);

  return secondsLeft;
}

export function CheckEmailPage() {
  const { resend } = useAuth();
  const location = useLocation();
  const stateEmail = (location.state as { email?: string } | null)?.email;
  // localStorage survives a reload; router state covers browsers where storage is blocked.
  const [pending, setPending] = useState<PendingSignup | null>(() => getPendingSignup());
  const email = stateEmail ?? pending?.email;
  const secondsLeft = useSecondsUntil(pending?.resendAvailableAt ?? 0);
  const [sending, setSending] = useState(false);
  const [status, setStatus] = useState<Status>(null);

  if (!email) {
    return (
      <AuthLayout
        title="Check your email"
        subtitle="Sign up first and we'll send you a verification link."
        icon={<Mail aria-hidden />}
      >
        <ButtonLink to="/signup">Go to sign up</ButtonLink>
      </AuthLayout>
    );
  }

  async function handleResend() {
    if (!email) return;
    setSending(true);
    setStatus(null);
    const { error } = await resend(email);
    setSending(false);
    // Restart the cooldown on success, and also on a rate-limit error (Supabase's own
    // timer is still running, so let the countdown catch up with it).
    if (!error || error.code === "over_email_send_rate_limit") {
      setPending(startPendingSignup(email));
    }
    setStatus(
      error
        ? { variant: "error", message: authErrorMessage(error) ?? "" }
        : { variant: "success", message: `We sent a new link to ${email}.` },
    );
  }

  return (
    <AuthLayout
      title="Check your email"
      subtitle={
        <>
          We sent a verification link to{" "}
          <span className="font-semibold break-all text-text">{email}</span>
        </>
      }
      icon={<Mail aria-hidden />}
    >
      {status && <Alert variant={status.variant}>{status.message}</Alert>}
      <div className="flex flex-col items-center gap-4">
        <Button
          variant="secondary"
          onClick={handleResend}
          loading={sending}
          disabled={secondsLeft > 0}
        >
          {secondsLeft > 0 ? `Resend in ${secondsLeft}s` : "Resend email"}
        </Button>
        <TextLink to="/signup" variant="muted" className="-my-3">
          Wrong email? Back to sign up
        </TextLink>
      </div>
    </AuthLayout>
  );
}
