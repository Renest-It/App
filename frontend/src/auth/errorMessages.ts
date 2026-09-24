import type { AuthError } from "@supabase/supabase-js";
import { PASSWORD_MIN_LENGTH } from "./validation";

export const GENERIC_ERROR = "Something went wrong. Please try again.";

// Maps Supabase's error *codes* to our own wording. Never show error.message to users:
// it's written for developers and can change between Supabase versions.
const messages: Record<string, string> = {
  // Supabase uses this for both "wrong password" and "no such account" on purpose, so it
  // doesn't reveal which emails are registered. We can't tell them apart either.
  invalid_credentials: "Email or password is incorrect.",
  email_not_confirmed: "Your email isn't verified yet. Check your inbox for the link.",
  over_email_send_rate_limit: "Please wait a minute before requesting another email.",
  over_request_rate_limit: "Too many attempts. Please wait a minute and try again.",
  weak_password: `Password must be at least ${PASSWORD_MIN_LENGTH} characters.`,
  email_address_invalid: "Enter a valid email address.",
};

export function authErrorMessage(error: AuthError | null | undefined) {
  if (!error) return null;
  return (error.code && messages[error.code]) || GENERIC_ERROR;
}
