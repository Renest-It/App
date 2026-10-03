import { useId, type InputHTMLAttributes } from "react";

type PriceInputProps = Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "value"> & {
  label: string;
  error?: string;
  // The raw text the user typed (e.g. "45" or "12.50"), not cents. The page converts to
  // cents at submit/validation time — see listings/validation.ts.
  value: string;
};

// A dollar amount, typed as plain text so "45.00" isn't fought by a native number input's
// stepper/scroll-to-change behavior. inputMode="decimal" still gives phones a number pad.
export function PriceInput({
  label,
  error,
  id,
  value,
  className = "",
  ...inputProps
}: PriceInputProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const errorId = `${inputId}-error`;

  return (
    <div className="flex w-full flex-col gap-2">
      <label htmlFor={inputId} className="text-sm font-semibold text-text">
        {label}
      </label>
      <div className="relative">
        <span
          aria-hidden
          className="pointer-events-none absolute top-1/2 left-4 -translate-y-1/2 font-semibold text-text-muted"
        >
          $
        </span>
        <input
          id={inputId}
          type="text"
          inputMode="decimal"
          value={value}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
          // 16px text, like TextField: smaller makes iOS Safari zoom in on focus.
          className={
            `h-12 w-full rounded-md border-[1.5px] bg-surface pr-4 pl-7 text-base text-text ` +
            `placeholder:text-text-placeholder focus:outline-none focus:ring-3 ` +
            (error
              ? "border-danger focus:ring-danger/15 "
              : "border-border focus:border-accent focus:ring-accent/15 ") +
            className
          }

          {...inputProps}
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
