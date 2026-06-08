import { useId, type SelectHTMLAttributes } from "react";

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  hint?: string;
  error?: string;
}

export default function Select({
  label,
  hint,
  error,
  id,
  className = "",
  children,
  "aria-describedby": ariaDescribedBy,
  "aria-invalid": ariaInvalid,
  ...props
}: SelectProps) {
  const generatedId = useId();
  const selectId = id ?? props.name ?? generatedId;
  const internalDescriptionId = error ? `${selectId}-error` : hint ? `${selectId}-hint` : undefined;
  const describedBy = Array.from(
    new Set([...(ariaDescribedBy?.split(/\s+/) ?? []), internalDescriptionId].filter(Boolean)),
  ).join(" ");

  return (
    <div className="block">
      {label ? (
        <label
          htmlFor={selectId}
          className="mb-1.5 block text-xs font-semibold uppercase tracking-[0.14em] text-[var(--ukip-muted)]"
        >
          {label}
        </label>
      ) : null}
      <select
        id={selectId}
        aria-describedby={describedBy || undefined}
        aria-invalid={error ? true : ariaInvalid}
        className={`ukip-focus h-10 w-full rounded-[var(--ukip-radius-md)] border border-[var(--ukip-border)] bg-[var(--ukip-panel)] px-3 text-sm text-[var(--ukip-text)] ${className}`}
        {...props}
      >
        {children}
      </select>
      {error ? (
        <span id={`${selectId}-error`} className="mt-1.5 block text-xs font-medium text-[var(--ukip-danger)]">
          {error}
        </span>
      ) : hint ? (
        <span id={`${selectId}-hint`} className="mt-1.5 block text-xs text-[var(--ukip-muted)]">
          {hint}
        </span>
      ) : null}
    </div>
  );
}

