import type { ReactNode, TextareaHTMLAttributes } from "react";
import { FieldLabel, FieldMessages, useFieldChrome } from "./Field";

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
}

export default function Textarea({
  label,
  hint,
  error,
  id,
  className = "",
  required,
  "aria-describedby": describedBy,
  ...props
}: TextareaProps) {
  const { controlId, hintId, errorId, ariaDescribedBy } = useFieldChrome({
    id: id ?? props.name,
    describedBy,
    hint,
    error,
  });

  return (
    <div className="block">
      {label ? <FieldLabel htmlFor={controlId} required={required}>{label}</FieldLabel> : null}
      <textarea
        id={controlId}
        aria-describedby={ariaDescribedBy}
        aria-invalid={Boolean(error) || undefined}
        required={required}
        className={`ukip-control ukip-focus min-h-28 resize-y ${className}`}
        {...props}
      />
      <FieldMessages error={error} errorId={errorId} hint={hint} hintId={hintId} />
    </div>
  );
}
