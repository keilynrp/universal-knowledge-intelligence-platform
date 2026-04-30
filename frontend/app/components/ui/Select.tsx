import type { SelectHTMLAttributes } from "react";

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  hint?: string;
  error?: string;
}

export default function Select({ label, hint, error, id, className = "", children, ...props }: SelectProps) {
  const selectId = id ?? props.name;

  return (
    <label className="block">
      {label ? (
        <span className="mb-1.5 block text-xs font-semibold uppercase tracking-[0.14em] text-[var(--ukip-muted)]">
          {label}
        </span>
      ) : null}
      <select
        id={selectId}
        className={`ukip-focus h-10 w-full rounded-[var(--ukip-radius-md)] border border-[var(--ukip-border)] bg-[var(--ukip-panel)] px-3 text-sm text-[var(--ukip-text)] ${className}`}
        {...props}
      >
        {children}
      </select>
      {error ? (
        <span className="mt-1.5 block text-xs font-medium text-[var(--ukip-danger)]">{error}</span>
      ) : hint ? (
        <span className="mt-1.5 block text-xs text-[var(--ukip-muted)]">{hint}</span>
      ) : null}
    </label>
  );
}

