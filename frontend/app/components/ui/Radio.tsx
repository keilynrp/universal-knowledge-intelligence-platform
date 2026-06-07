import type { InputHTMLAttributes, ReactNode } from "react";
import { FieldMessages, useFieldChrome } from "./Field";

export interface RadioProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
}

export default function Radio({
  label,
  hint,
  error,
  id,
  className = "",
  required,
  "aria-describedby": describedBy,
  ...props
}: RadioProps) {
  const { controlId, hintId, errorId, ariaDescribedBy } = useFieldChrome({
    id: id ?? props.name,
    describedBy,
    hint,
    error,
  });

  return (
    <div>
      <label className="inline-flex min-h-11 cursor-pointer items-center gap-3 text-sm font-medium text-[var(--ukip-text)]">
        <input
          {...props}
          id={controlId}
          type="radio"
          required={required}
          aria-describedby={ariaDescribedBy}
          className={`ukip-check-control ukip-focus ${className}`}
        />
        <span>{label}</span>
      </label>
      <FieldMessages error={error} errorId={errorId} hint={hint} hintId={hintId} />
    </div>
  );
}
