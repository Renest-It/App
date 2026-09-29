import { Check, TriangleAlert } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { Alert } from "../components/Alert";
import { AuthLayout } from "../components/AuthLayout";
import { Button, ButtonLink } from "../components/Button";
import { TextField } from "../components/TextField";
import { TextLink } from "../components/TextLink";
import { authErrorMessage } from "../auth/errorMessages";
import { getPendingSignup, startPendingSignup } from "../auth/pendingSignup";
import { useAuth } from "../auth/useAuth";
import { looksComplete, normalizeEmail } from "../auth/validation";

// Supabase sends failed verification links back with the reason in the URL fragment
// (e.g. #error=access_denied&error_code=otp_expired), or occasionally in the query string.
function readLinkError() {
  const hash = new URLSearchParams(window.location.hash.slice(1));
  const query = new URLSearchParams(window.location.search);
  return (
    hash.get("error_code") ?? hash.get("error") ?? query.get("error_code") ?? query.get("error")
  );
}

export function ConfirmPage() {
  const { session, loading } = useAuth();
  // Read once, on first render: supabase-js cleans up the URL after it processes the link.
  const [linkError] = useState(readLinkError);

  if (linkError) return <ExpiredLink />;
  if (loading) return null;
  // A working link signs the user in (on whatever device opened it). No session and no error
  // means the link was bad or the page was opened directly.
  return session ? <Verified /> : <ExpiredLink />;
}

function Verified() {
  return (
    <AuthLayout
      title="You're verified!"
      subtitle="Your Creighton email has been successfully confirmed. You're ready to explore and trade."
      icon={<Check aria-hidden strokeWidth={3} />}
      iconTone="success"
    >
      {/* The user is already signed in, so /login forwards them to Home. */}
      <ButtonLink to="/login">Log in</ButtonLink>
    </AuthLayout>
  );
}

function ExpiredLink() {
  const { resend } = useAuth();
  const navigate = useNavigate();
  // Known if they signed up in this browser; a phone that only opened the link won't know it.
  const [knownEmail] = useState(() => getPendingSignup()?.email);
  const [email, setEmail] = useState(knownEmail ?? "");
  const [fieldError, setFieldError] = useState<string>();
  const [formError, setFormError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  async function handleResend(e: FormEvent) {
    e.preventDefault();
    const address = normalizeEmail(email);
    if (!looksComplete(address)) {
      setFieldError("Enter the email you signed up with");
      return;
    }
    setFieldError(undefined);
    setFormError(null);
    setSending(true);
    const { error } = await resend(address);
    setSending(false);
    if (error) {
      setFormError(authErrorMessage(error));
      return;
    }
    startPendingSignup(address);
    navigate("/check-email", { state: { email: address } });
  }

  return (
    <AuthLayout
      title="Link expired"
      subtitle="This verification link has expired or is no longer valid. Let's send you a fresh link."
      icon={<TriangleAlert aria-hidden />}
      iconTone="danger"
    >
      {formError && <Alert>{formError}</Alert>}
      <form noValidate onSubmit={handleResend} className="flex flex-col gap-7">
        {!knownEmail && (
          <TextField
            label="Creighton Email"
            name="email"
            type="email"
            inputMode="email"
            autoComplete="email"
            autoCapitalize="none"
            spellCheck={false}
            placeholder="you@creighton.edu"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            error={fieldError}
          />
        )}
        <div className="flex flex-col items-center gap-4">
          <Button type="submit" loading={sending}>
            Resend verification email
          </Button>
          <p className="-my-3 flex items-center gap-1 text-sm text-text-muted">
            Wrong email? <TextLink to="/signup">Back to sign up</TextLink>
          </p>
        </div>
      </form>
    </AuthLayout>
  );
}
