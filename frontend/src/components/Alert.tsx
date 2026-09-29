import { CircleAlert, CircleCheck, Info, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

type Variant = "error" | "success" | "info";

const styles: Record<Variant, { box: string; icon: string; Icon: LucideIcon }> = {
  error: {
    box: "border-danger-border bg-danger-soft text-danger-text",
    icon: "text-danger",
    Icon: CircleAlert,
  },
  // Figma only defines the error banner; success and info reuse the matching theme colors.
  success: {
    box: "border-success/30 bg-success-soft text-text",
    icon: "text-success",
    Icon: CircleCheck,
  },
  info: { box: "border-accent/20 bg-accent-soft text-text", icon: "text-accent", Icon: Info },
};

type AlertProps = { variant?: Variant; children: ReactNode };

export function Alert({ variant = "error", children }: AlertProps) {
  const { box, icon, Icon } = styles[variant];
  return (
    // role="alert" makes screen readers announce errors as soon as they appear.
    <div
      role={variant === "error" ? "alert" : "status"}
      className={`flex w-full items-center gap-3 rounded-md border p-3 text-sm font-medium ${box}`}
    >
      <Icon aria-hidden className={`size-4.5 shrink-0 ${icon}`} />
      <div className="flex-1">{children}</div>
    </div>
  );
}
