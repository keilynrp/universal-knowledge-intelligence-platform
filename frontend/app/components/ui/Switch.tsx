import { useId, type ReactNode } from "react";

export interface SwitchProps {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  label: ReactNode;
  description?: ReactNode;
  disabled?: boolean;
  id?: string;
  className?: string;
}

export default function Switch({
  checked,
  onCheckedChange,
  label,
  description,
  disabled = false,
  id,
  className = "",
}: SwitchProps) {
  const generatedId = useId();
  const switchId = id ?? `ukip-switch-${generatedId.replace(/:/g, "")}`;
  const labelId = `${switchId}-label`;
  const descriptionId = description ? `${switchId}-description` : undefined;

  return (
    <div className={`flex min-h-11 items-center justify-between gap-4 ${className}`}>
      <div className="min-w-0">
        <label className="cursor-pointer text-sm font-semibold text-[var(--ukip-text)]" htmlFor={switchId} id={labelId}>
          {label}
        </label>
        {description ? (
          <p className="mt-0.5 text-xs leading-5 text-[var(--ukip-muted)]" id={descriptionId}>
            {description}
          </p>
        ) : null}
      </div>
      <button
        id={switchId}
        type="button"
        role="switch"
        aria-checked={checked}
        aria-labelledby={labelId}
        aria-describedby={descriptionId}
        disabled={disabled}
        onClick={() => onCheckedChange(!checked)}
        className="ukip-focus ukip-switch-track disabled:cursor-not-allowed disabled:opacity-55"
      >
        <span aria-hidden="true" className="ukip-switch-thumb" />
      </button>
    </div>
  );
}
