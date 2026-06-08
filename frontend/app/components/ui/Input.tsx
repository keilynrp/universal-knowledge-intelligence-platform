import type { InputHTMLAttributes, ReactNode } from "react";
import { FieldLabel, FieldMessages, useFieldChrome } from "./Field";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
}

export default function Input({
  label,
  hint,
  error,
  id,
  className = "",
  required,
  "aria-describedby": describedBy,
  "aria-invalid": ariaInvalid,
  ...props
}: InputProps) {
  const { controlId, hintId, errorId, ariaDescribedBy } = useFieldChrome({
    id: id ?? props.name,
    describedBy,
    hint,
    error,
  });

  return (
    <div className="block">
      {label ? <FieldLabel htmlFor={controlId} required={required}>{label}</FieldLabel> : null}
      <input
        id={controlId}
        aria-describedby={ariaDescribedBy}
        aria-invalid={error ? true : ariaInvalid}
        required={required}
        className={`ukip-control ukip-focus h-10 ${className}`}
        {...props}
      />
      <FieldMessages error={error} errorId={errorId} hint={hint} hintId={hintId} />
    </div>
  );
}

