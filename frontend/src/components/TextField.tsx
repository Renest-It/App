import { useId, type InputHTMLAttributes } from "react";

type TextFieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  error?: string;
};

export function TextField({ label, error, id, className = "", ...inputProps }: TextFieldProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const errorId = `${inputId}-error`;

  return (
    <div className="flex w-full flex-col gap-2">
      <label htmlFor={inputId} className="text-sm font-semibold text-text">
        {label}
      </label>
      <input
        id={inputId}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        // 16px text (not Figma's 15px): anything smaller makes iOS Safari zoom in on focus.
        className={
          `h-12 w-full rounded-md border-[1.5px] bg-surface px-4 text-base text-text ` +
          `placeholder:text-text-placeholder focus:outline-none focus:ring-3 ` +
          (error
            ? "border-danger focus:ring-danger/15 "
            : "border-border focus:border-accent focus:ring-accent/15 ") +
          className
        }
        {...inputProps}
      />
      {error && (
        <p id={errorId} className="text-caption font-medium text-danger-text">
          {error}
        </p>
      )}
    </div>
  );
}
