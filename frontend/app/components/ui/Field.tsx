import { useId, type ReactNode } from "react";

export interface FieldChromeProps {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  required?: boolean;
  id?: string;
  describedBy?: string;
}

export function useFieldChrome({
  id,
  describedBy,
  hint,
  error,
}: Pick<FieldChromeProps, "id" | "describedBy" | "hint" | "error">) {
  const generatedId = useId();
  const controlId = id ?? `ukip-field-${generatedId.replace(/:/g, "")}`;
  const hintId = hint && !error ? `${controlId}-hint` : undefined;
  const errorId = error ? `${controlId}-error` : undefined;
  const ariaDescribedBy =
    Array.from(
      new Set([...(describedBy?.split(/\s+/) ?? []), hintId, errorId].filter(Boolean)),
    ).join(" ") || undefined;

  return { controlId, hintId, errorId, ariaDescribedBy };
}

export function FieldLabel({
  htmlFor,
  children,
  required,
}: {
  htmlFor: string;
  children: ReactNode;
  required?: boolean;
}) {
  return (
    <label className="ukip-field-label" htmlFor={htmlFor}>
      {children}
      {required ? (
        <span aria-hidden="true" className="ukip-field-required">
          *
        </span>
      ) : null}
    </label>
  );
}

export function FieldMessages({
  hint,
  error,
  hintId,
  errorId,
}: {
  hint?: ReactNode;
  error?: ReactNode;
  hintId?: string;
  errorId?: string;
}) {
  return (
    <>
      {hint && !error ? (
        <span className="ukip-field-message" id={hintId}>
          {hint}
        </span>
      ) : null}
      {error ? (
        <span className="ukip-field-message ukip-field-message-error" id={errorId} role="alert">
          {error}
        </span>
      ) : null}
    </>
  );
}
