import { useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { Alert } from "../components/Alert";
import { AuthLayout } from "../components/AuthLayout";
import { Button } from "../components/Button";
import { TextField } from "../components/TextField";
import { TextLink } from "../components/TextLink";
import { authErrorMessage } from "../auth/errorMessages";
import { startPendingSignup } from "../auth/pendingSignup";
import { useAuth } from "../auth/useAuth";
import {
  PASSWORD_MIN_LENGTH,
  isCreightonEmail,
  looksComplete,
  normalizeEmail,
} from "../auth/validation";

const CREIGHTON_ERROR = "Use your @creighton.edu email";

type Fields = { displayName: string; email: string; password: string };

function validate({ displayName, email, password }: Fields) {
  return {
    displayName: displayName.trim() ? undefined : "Enter your name",
    email: !email.trim()
      ? "Enter your Creighton email"
      : !looksComplete(email)
        ? "Enter a valid email address"
        : !isCreightonEmail(email)
          ? CREIGHTON_ERROR
          : undefined,
    password: !password
      ? "Enter a password"
      : password.length < PASSWORD_MIN_LENGTH
        ? `Password must be at least ${PASSWORD_MIN_LENGTH} characters`
        : undefined,
  };
}

export function SignUpPage() {
  const { signUp } = useAuth();
  const navigate = useNavigate();
  const [fields, setFields] = useState<Fields>({ displayName: "", email: "", password: "" });
  const [attempted, setAttempted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const [formError, setFormError] = useState<string | null>(null);

  const errors = validate(fields);
  // Before the first submit, only the instant Creighton check shows (and only once the
  // address looks complete). After a submit attempt, every field shows its error live.
  const shown = attempted
    ? errors
    : {
        displayName: undefined,
        email:
          looksComplete(fields.email) && !isCreightonEmail(fields.email)
            ? CREIGHTON_ERROR
            : undefined,
        password: undefined,
      };

  function update(name: keyof Fields) {
    return (e: ChangeEvent<HTMLInputElement>) =>
      setFields((f) => ({ ...f, [name]: e.target.value }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setAttempted(true);
    if (errors.displayName || errors.email || errors.password) return;
    // A ref, not state: two quick Enter presses can both run before a re-render.
    if (submittingRef.current) return;
    submittingRef.current = true;
    setSubmitting(true);
    setFormError(null);

    const email = normalizeEmail(fields.email);
    const { error } = await signUp(email, fields.password, fields.displayName.trim());

    submittingRef.current = false;
    setSubmitting(false);
    if (error) {
      setFormError(authErrorMessage(error));
      return;
    }
    // Note: Supabase also reports success for an already-registered email (so nobody can
    // probe which emails have accounts). "Check your email" is the right screen either way.
    startPendingSignup(email);
    navigate("/check-email", { state: { email } });
  }

  return (
    <AuthLayout title="Create your account" subtitle="Creighton email required to verify identity">
      {formError && <Alert>{formError}</Alert>}
      <form noValidate onSubmit={handleSubmit} className="flex flex-col gap-7">
        <div className="flex flex-col gap-4">
          <TextField
            label="Display Name"
            name="displayName"
            autoComplete="name"
            placeholder="Your name"
            value={fields.displayName}
            onChange={update("displayName")}
            error={shown.displayName}
          />
          <TextField
            label="Creighton Email"
            name="email"
            type="email"
            inputMode="email"
            autoComplete="email"
            autoCapitalize="none"
            spellCheck={false}
            placeholder="you@creighton.edu"
            value={fields.email}
            onChange={update("email")}
            error={shown.email}
          />
          <TextField
            label="Password"
            name="password"
            type="password"
            autoComplete="new-password"
            placeholder="••••••••"
            value={fields.password}
            onChange={update("password")}
            error={shown.password}
          />
        </div>
        <div className="flex flex-col items-center gap-4">
          <Button type="submit" loading={submitting}>
            Create account
          </Button>
          {/* Negative margin keeps Figma's spacing while the link keeps a 44px tap area. */}
          <p className="-my-3 flex items-center gap-1 text-sm text-text-muted">
            Already have an account? <TextLink to="/login">Log in</TextLink>
          </p>
        </div>
      </form>
    </AuthLayout>
  );
}
