import type { ListingStatus } from "../api/types";

const styles: Record<ListingStatus, { label: string; className: string }> = {
  draft: { label: "Draft", className: "bg-border text-text-muted" },
  active: { label: "Active", className: "bg-success-soft text-text" },
  sold: { label: "Sold", className: "bg-text text-surface" },
};

// A listing's status as a small pill (E3.4). Presentational only, like CategoryChip.
export function StatusBadge({ status }: { status: ListingStatus }) {
  const { label, className } = styles[status];
  return (
    <span className={`inline-block rounded-full px-2.5 py-1 text-xs font-semibold ${className}`}>
      {label}
    </span>
  );
}
