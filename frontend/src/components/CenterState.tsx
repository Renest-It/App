import type { ReactNode } from "react";

// A centered icon, heading, and message with an action below: the listing pages' not-found
// and error states.
export function CenterState({
  icon,
  title,
  body,
  danger = false,
  children,
}: {
  icon: ReactNode;
  title: string;
  body: string;
  danger?: boolean;
  children: ReactNode;
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
      <h1 className="font-display text-lg font-bold text-text">{title}</h1>
      <p className="text-body max-w-xs text-text-muted">{body}</p>
      {children}
    </div>
  );
}
