import { useId, type TextareaHTMLAttributes } from "react";

type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label: string;
  error?: string;
  maxLength?: number;
};

// Same box/label/error pattern as TextField, plus a character counter for maxLength fields
// (the description field is the only user of this so far: up to 2,000 characters).
export function Textarea({
  label,
  error,
  id,
  maxLength,
  value,
  className = "",
  ...textareaProps
}: TextareaProps) {
  const generatedId = useId();
  const textareaId = id ?? generatedId;
  const errorId = `${textareaId}-error`;
  const counterId = `${textareaId}-counter`;
  const length = typeof value === "string" ? value.length : 0;

  return (
    <div className="flex w-full flex-col gap-2">
      <div className="flex items-baseline justify-between gap-2">
        <label htmlFor={textareaId} className="text-sm font-semibold text-text">
          {label}
        </label>
        {maxLength !== undefined && (
          <span id={counterId} className="text-caption text-text-placeholder">
            {length}/{maxLength}
          </span>
        )}
      </div>
      <textarea
        id={textareaId}
        value={value}
        maxLength={maxLength}
        aria-invalid={error ? true : undefined}
        aria-describedby={
          [error ? errorId : null, maxLength !== undefined ? counterId : null]
            .filter(Boolean)
            .join(" ") || undefined
        }
        // 16px text, like TextField: smaller makes iOS Safari zoom in on focus.
        className={
          `min-h-28 w-full resize-y rounded-md border-[1.5px] bg-surface px-4 py-3 text-base text-text ` +
          `placeholder:text-text-placeholder focus:outline-none focus:ring-3 ` +
          (error
            ? "border-danger focus:ring-danger/15 "
            : "border-border focus:border-accent focus:ring-accent/15 ") +
          className
        }
        {...textareaProps}
      />
      {error && (
        <p id={errorId} className="text-caption font-medium text-danger-text">
          {error}
        </p>
      )}
    </div>
  );
}
