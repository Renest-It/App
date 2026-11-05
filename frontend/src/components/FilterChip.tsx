type FilterChipProps = {
  label: string;
  selected: boolean;
  onClick: () => void;
  // For the component gallery's always-focused example only.
  className?: string;
};

// One pill in the home feed's filter bar (Figma 3:34 desktop, 11:27 mobile): filled accent when
// selected, outlined otherwise. A toggle button, so screen readers announce "pressed". The
// static category label on cards is CategoryChip, which is deliberately not a control.
export function FilterChip({ label, selected, onClick, className = "" }: FilterChipProps) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onClick}
      className={
        // min-h-11: a 44px tap target, 4px taller than Figma's 40px pill.
        "flex min-h-11 shrink-0 items-center rounded-full border px-5 text-body leading-5 " +
        "font-semibold whitespace-nowrap transition-colors " +
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent " +
        (selected
          ? "border-accent bg-accent text-surface"
          : "border-border bg-surface text-text-muted hover:bg-bg") +
        ` ${className}`
      }
    >
      {label}
    </button>
  );
}
