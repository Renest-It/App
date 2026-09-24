import { LoaderCircle } from "lucide-react";
import type { ButtonHTMLAttributes } from "react";
import { Link, type LinkProps } from "react-router";

type Variant = "primary" | "secondary" | "danger";

const base =
  // Height comes from min-h-12 (48px), not vertical padding, so bordered variants
  // (secondary, danger) are the same height as primary.
  "flex min-h-12 w-full items-center justify-center gap-2 rounded-md px-6 py-2 " +
  "text-body leading-5 font-semibold transition-colors " +
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent " +
  "disabled:cursor-not-allowed disabled:opacity-60";

const variants: Record<Variant, string> = {
  primary: "bg-accent text-surface hover:bg-accent/90",
  secondary: "border border-border bg-surface text-text-muted hover:bg-bg",
  // Destructive actions such as Log Out. Figma's lighter red text is too low-contrast on the
  // pink background, so the text uses danger-text (see ADR 0008 / E1.3 design notes).
  danger: "border border-danger bg-danger-soft text-danger-text hover:bg-danger-soft-strong",
};

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  // Shows a spinner and disables the button, so a slow request can't be submitted twice.
  loading?: boolean;
};

export function Button({
  variant = "primary",
  loading = false,
  disabled,
  type = "button",
  className = "",
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={`${base} ${variants[variant]} ${className}`}
      {...props}
    >
      {loading && <LoaderCircle aria-hidden className="size-4.5 animate-spin" />}
      {children}
    </button>
  );
}

type ButtonLinkProps = LinkProps & { variant?: Variant };

// A navigation link that looks like a Button (e.g. "Log in" on the verified screen).
export function ButtonLink({ variant = "primary", className = "", ...props }: ButtonLinkProps) {
  return <Link className={`${base} ${variants[variant]} ${className}`} {...props} />;
}
