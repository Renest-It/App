import type { ReactNode } from "react";
import logoUrl from "../assets/renest-logo.svg";

type IconTone = "accent" | "danger" | "success";

const iconTones: Record<IconTone, string> = {
  accent: "bg-accent-soft text-accent",
  danger: "bg-danger-soft-strong text-danger",
  success: "bg-success-soft text-success",
};

type AuthLayoutProps = {
  title: string;
  subtitle?: ReactNode;
  // Optional Lucide icon shown in a tinted circle above the title (check email, verified, expired).
  icon?: ReactNode;
  iconTone?: IconTone;
  children: ReactNode;
};

export function AuthLayout({
  title,
  subtitle,
  icon,
  iconTone = "accent",
  children,
}: AuthLayoutProps) {
  return (
    // Safe-area padding pairs with viewport-fit=cover in index.html, keeping content clear of the notch.
    <div
      className={
        "flex min-h-dvh flex-col items-center gap-6 bg-bg " +
        "px-[max(1.25rem,env(safe-area-inset-left))] pt-[max(1.25rem,env(safe-area-inset-top))] " +
        "pb-[max(1.25rem,env(safe-area-inset-bottom))] " +
        "sm:justify-center sm:gap-8 sm:p-10"
      }
    >
      <header className="flex flex-col items-center gap-3">
        <div className="flex items-center gap-2">
          <img src={logoUrl} alt="" width={36} height={32} />
          <span className="text-heading font-bold text-text">ReNest</span>
        </div>
        <span className="rounded-sm bg-accent-soft px-2.5 py-1 text-xs font-semibold text-accent">
          Creighton Verified Marketplace
        </span>
      </header>

      <main className="flex w-full flex-col gap-7 rounded-lg border border-border bg-surface p-8 sm:w-115">
        {icon && (
          <div
            className={
              `mx-auto flex size-16 items-center justify-center rounded-full sm:size-18 ` +
              `[&>svg]:size-7 sm:[&>svg]:size-8 ${iconTones[iconTone]}`
            }
          >
            {icon}
          </div>
        )}
        <div className="flex flex-col items-center gap-2 text-center">
          <h1 className="font-display text-heading font-bold text-text sm:text-2xl">{title}</h1>
          {subtitle && <p className="text-body leading-normal text-text-muted">{subtitle}</p>}
        </div>
        {children}
      </main>
    </div>
  );
}
