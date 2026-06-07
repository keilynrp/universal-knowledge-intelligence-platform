import type { ReactNode, SelectHTMLAttributes } from "react";
import { FieldLabel, FieldMessages, useFieldChrome } from "./Field";

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
}

export default function Select({
  label,
  hint,
  error,
  id,
  className = "",
  children,
  required,
  "aria-describedby": describedBy,
  ...props
}: SelectProps) {
  const { controlId, hintId, errorId, ariaDescribedBy } = useFieldChrome({
    id: id ?? props.name,
    describedBy,
    hint,
    error,
  });

  return (
    <div className="block">
      {label ? <FieldLabel htmlFor={controlId} required={required}>{label}</FieldLabel> : null}
      <select
        id={controlId}
        aria-describedby={ariaDescribedBy}
        aria-invalid={Boolean(error) || undefined}
        required={required}
        className={`ukip-control ukip-focus ${className}`}
        {...props}
      >
        {children}
      </select>
      <FieldMessages error={error} errorId={errorId} hint={hint} hintId={hintId} />
    </div>
  );
}

