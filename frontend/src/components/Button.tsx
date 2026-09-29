import { LoaderCircle } from "lucide-react";
import type { ButtonHTMLAttributes } from "react";
import { Link, type LinkProps } from "react-router";

type Variant = "primary" | "secondary";

const base =
  "flex min-h-12 w-full items-center justify-center gap-2 rounded-md px-6 py-3.5 " +
  "text-body leading-5 font-semibold transition-colors " +
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent " +
  "disabled:cursor-not-allowed disabled:opacity-60";

const variants: Record<Variant, string> = {
  primary: "bg-accent text-surface hover:bg-accent/90",
  secondary: "border border-border bg-surface text-text-muted hover:bg-bg",
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
