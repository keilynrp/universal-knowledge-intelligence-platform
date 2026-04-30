import type { InputHTMLAttributes } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
  error?: string;
}

export default function Input({ label, hint, error, id, className = "", ...props }: InputProps) {
  const inputId = id ?? props.name;

  return (
    <label className="block">
      {label ? (
        <span className="mb-1.5 block text-xs font-semibold uppercase tracking-[0.14em] text-[var(--ukip-muted)]">
          {label}
        </span>
      ) : null}
      <input
        id={inputId}
        className={`ukip-focus h-10 w-full rounded-[var(--ukip-radius-md)] border border-[var(--ukip-border)] bg-[var(--ukip-panel)] px-3 text-sm text-[var(--ukip-text)] placeholder:text-[var(--ukip-muted-soft)] ${className}`}
        {...props}
      />
      {error ? (
        <span className="mt-1.5 block text-xs font-medium text-[var(--ukip-danger)]">{error}</span>
      ) : hint ? (
        <span className="mt-1.5 block text-xs text-[var(--ukip-muted)]">{hint}</span>
      ) : null}
    </label>
  );
}

