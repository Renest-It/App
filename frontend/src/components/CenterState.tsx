import type { ReactNode } from "react";

// A centered icon, heading, and message with an optional action below: the listing pages'
// not-found, error, and empty states.
export function CenterState({
  icon,
  title,
  body,
  danger = false,
  heading: Heading = "h1",
  children,
}: {
  icon: ReactNode;
  title: string;
  body: string;
  danger?: boolean;
  // h2 when the page already has its own h1 (My Listings' empty tabs).
  heading?: "h1" | "h2";
  children?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 px-4 py-16 text-center">
      <div
        className={
          "flex size-14 items-center justify-center rounded-full " +
          (danger ? "bg-danger-soft-strong text-danger" : "bg-accent-soft text-accent")
        }
      >
        {icon}
      </div>
      <Heading className="font-display text-lg font-bold text-text">{title}</Heading>
      <p className="text-body max-w-xs text-text-muted">{body}</p>
      {children}
    </div>
  );
}
