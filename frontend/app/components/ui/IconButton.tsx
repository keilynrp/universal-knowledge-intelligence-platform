import type { ButtonHTMLAttributes } from "react";

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: string;
}

export default function IconButton({ label, className = "", type = "button", children, ...props }: IconButtonProps) {
  return (
    <button
      type={type}
      aria-label={label}
      title={label}
      className={`ukip-focus inline-flex h-10 w-10 items-center justify-center rounded-full border border-[var(--ukip-border)] bg-[var(--ukip-panel)] text-[var(--ukip-muted)] transition hover:bg-[var(--ukip-panel-strong)] hover:text-[var(--ukip-text-strong)] ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

