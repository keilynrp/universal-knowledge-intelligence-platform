import type { LabelHTMLAttributes } from "react";

export interface LabelProps extends LabelHTMLAttributes<HTMLLabelElement> {
  required?: boolean;
}

export default function Label({ children, className = "", required, ...props }: LabelProps) {
  return (
    <label className={`ukip-field-label ${className}`} {...props}>
      {children}
      {required ? (
        <span aria-hidden="true" className="ukip-field-required">
          *
        </span>
      ) : null}
    </label>
  );
}
