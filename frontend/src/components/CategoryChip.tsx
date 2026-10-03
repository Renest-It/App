type CategoryChipProps = {
  label: string;
};

// A listing's category, shown as a small pill (E2.0 mockup: the detail page and the home
// card both show the category this way). Presentational only — not a control.
export function CategoryChip({ label }: CategoryChipProps) {
  return (
    <span className="inline-block rounded-full bg-accent-soft px-2.5 py-1 text-xs font-semibold text-accent">
      {label}
    </span>
  );
}
