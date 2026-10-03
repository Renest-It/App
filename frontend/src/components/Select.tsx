import { ChevronDown } from "lucide-react";
import { useId, type ReactNode, type SelectHTMLAttributes } from "react";

type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & {
  label: string;
  error?: string;
  children: ReactNode;
};

// Same box/label/error pattern as TextField, with a chevron since a native <select> gives
// no other visual hint that it opens a menu.
export function Select({
  label,
  error,
  id,
  className = "",
  children,
  ...selectProps
}: SelectProps) {
  const generatedId = useId();
  const selectId = id ?? generatedId;
  const errorId = `${selectId}-error`;

  return (
    <div className="flex w-full flex-col gap-2">
      <label htmlFor={selectId} className="text-sm font-semibold text-text">
        {label}
      </label>
      <div className="relative">
        <select
          id={selectId}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
          // 16px text, like TextField: smaller makes iOS Safari zoom in on focus.
          className={
            `h-12 w-full appearance-none rounded-md border-[1.5px] bg-surface px-4 pr-10 text-base text-text ` +
            `focus:outline-none focus:ring-3 ` +
            (error
              ? "border-danger focus:ring-danger/15 "
              : "border-border focus:border-accent focus:ring-accent/15 ") +
            className
          }
          {...selectProps}
        >
          {children}
        </select>
        <ChevronDown
          aria-hidden
          className="pointer-events-none absolute top-1/2 right-3 size-4.5 -translate-y-1/2 text-text-muted"
        />
      </div>
      {error && (
        <p id={errorId} className="text-caption font-medium text-danger-text">
          {error}
        </p>
      )}
    </div>
  );
}
