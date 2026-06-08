import { useId, type InputHTMLAttributes } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
  error?: string;
}

export default function Input({
  label,
  hint,
  error,
  id,
  className = "",
  "aria-describedby": ariaDescribedBy,
  "aria-invalid": ariaInvalid,
  ...props
}: InputProps) {
  const generatedId = useId();
  const inputId = id ?? props.name ?? generatedId;
  const internalDescriptionId = error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined;
  const describedBy = Array.from(
    new Set([...(ariaDescribedBy?.split(/\s+/) ?? []), internalDescriptionId].filter(Boolean)),
  ).join(" ");

  return (
    <div className="block">
      {label ? (
        <label
          htmlFor={inputId}
          className="mb-1.5 block text-xs font-semibold uppercase tracking-[0.14em] text-[var(--ukip-muted)]"
        >
          {label}
        </label>
      ) : null}
      <input
        id={inputId}
        aria-describedby={describedBy || undefined}
        aria-invalid={error ? true : ariaInvalid}
        className={`ukip-focus h-10 w-full rounded-[var(--ukip-radius-md)] border border-[var(--ukip-border)] bg-[var(--ukip-panel)] px-3 text-sm text-[var(--ukip-text)] placeholder:text-[var(--ukip-muted-soft)] ${className}`}
        {...props}
      />
      {error ? (
        <span id={`${inputId}-error`} className="mt-1.5 block text-xs font-medium text-[var(--ukip-danger)]">
          {error}
        </span>
      ) : hint ? (
        <span id={`${inputId}-hint`} className="mt-1.5 block text-xs text-[var(--ukip-muted)]">
          {hint}
        </span>
      ) : null}
    </div>
  );
}

