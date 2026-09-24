import { Link, type LinkProps } from "react-router";

type TextLinkProps = LinkProps & { variant?: "accent" | "muted" };

// Inline text link with a 44px-tall tap area, so small (14px) links are still easy to tap.
export function TextLink({ variant = "accent", className = "", ...props }: TextLinkProps) {
  const color = variant === "accent" ? "font-semibold text-accent" : "text-text-muted";
  return (
    <Link
      className={
        `inline-flex min-h-11 items-center text-sm hover:underline ` +
        `focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ` +
        `${color} ${className}`
      }
      {...props}
    />
  );
}
