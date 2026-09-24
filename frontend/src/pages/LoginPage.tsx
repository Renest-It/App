import type { AuthError } from "@supabase/supabase-js";
import { useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { Alert } from "../components/Alert";
import { AuthLayout } from "../components/AuthLayout";
import { Button } from "../components/Button";
import { TextField } from "../components/TextField";
import { TextLink } from "../components/TextLink";
import { authErrorMessage } from "../auth/errorMessages";
import { startPendingSignup } from "../auth/pendingSignup";
import { useAuth } from "../auth/useAuth";
import { normalizeEmail } from "../auth/validation";

export function LoginPage() {
  const { signIn, resend } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [attempted, setAttempted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const [error, setError] = useState<AuthError | null>(null);
  const [resending, setResending] = useState(false);

  const fieldErrors = attempted
    ? {
        email: email.trim() ? undefined : "Enter your email",
        password: password ? undefined : "Enter your password",
      }
    : {};

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setAttempted(true);
    if (!email.trim() || !password) return;
    // A ref, not state: two quick Enter presses can both run before a re-render.
    if (submittingRef.current) return;
    submittingRef.current = true;
    setSubmitting(true);
    setError(null);

    const { error } = await signIn(normalizeEmail(email), password);

    submittingRef.current = false;
    setSubmitting(false);
    if (error) {
      setError(error);
      return;
    }
    navigate("/", { replace: true });
  }

  async function handleResend() {
    const address = normalizeEmail(email);
    setResending(true);
    const { error: resendError } = await resend(address);
    setResending(false);
    if (resendError) {
      setError(resendError);
      return;
    }
    startPendingSignup(address);
    navigate("/check-email", { state: { email: address } });
  }

  const unverified = error?.code === "email_not_confirmed";

  return (
    <AuthLayout title="Log in to your account" subtitle="Welcome back to ReNest">
      {error && (
        <div className="flex flex-col gap-3">
          <Alert>{authErrorMessage(error)}</Alert>
          {unverified && (
            <Button variant="secondary" onClick={handleResend} loading={resending}>
              Resend verification email
            </Button>
          )}
        </div>
      )}
      <form noValidate onSubmit={handleSubmit} className="flex flex-col gap-7">
        <div className="flex flex-col gap-4">
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
            error={fieldErrors.email}
          />
          <TextField
            label="Password"
            name="password"
            type="password"
            autoComplete="current-password"
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={fieldErrors.password}
          />
        </div>
        <div className="flex flex-col items-center gap-4">
          <Button type="submit" loading={submitting}>
            Log in
          </Button>
          <p className="-my-3 flex items-center gap-1 text-sm text-text-muted">
            Don't have an account? <TextLink to="/signup">Sign up</TextLink>
          </p>
        </div>
      </form>
    </AuthLayout>
  );
}
