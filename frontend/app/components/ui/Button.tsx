import type { ButtonHTMLAttributes, ReactNode } from "react";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "outline" | "danger";
export type ButtonSize = "sm" | "md" | "lg" | "icon";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
  loading?: boolean;
  loadingLabel?: string;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary: "border-transparent bg-[var(--ukip-primary)] text-[var(--ukip-on-primary)] shadow-[var(--ukip-glow-violet)] hover:bg-[var(--ukip-primary-strong)]",
  secondary: "border-[var(--ukip-border)] bg-[var(--ukip-panel-strong)] text-[var(--ukip-text)] hover:border-[var(--ukip-border-strong)] hover:bg-[var(--ukip-control-hover)]",
  ghost: "border-transparent bg-transparent text-[var(--ukip-muted)] hover:bg-[var(--ukip-panel-strong)] hover:text-[var(--ukip-text-strong)]",
  outline: "border-[var(--ukip-border)] bg-transparent text-[var(--ukip-text)] hover:border-[var(--ukip-primary)] hover:bg-[var(--ukip-primary-soft)]",
  danger: "border-transparent bg-[var(--ukip-danger)] text-[var(--ukip-on-danger)] hover:brightness-110",
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "min-h-9 px-3 text-xs",
  md: "min-h-11 px-4 text-sm",
  lg: "min-h-12 px-5 text-sm",
  icon: "h-11 w-11 p-0",
};

export default function Button({
  children,
  className = "",
  variant = "primary",
  size = "md",
  leftIcon,
  rightIcon,
  loading = false,
  loadingLabel,
  type = "button",
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      aria-busy={loading || undefined}
      disabled={disabled || loading}
      className={`ukip-focus inline-flex touch-manipulation items-center justify-center gap-2 rounded-[var(--ukip-radius-md)] border font-semibold transition-[border-color,background-color,color,box-shadow,filter] disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-55 ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      {...props}
    >
      {loading ? <span aria-hidden="true" className="ukip-button-spinner" /> : leftIcon}
      <span>{loading && loadingLabel ? loadingLabel : children}</span>
      {loading ? null : rightIcon}
    </button>
  );
}
