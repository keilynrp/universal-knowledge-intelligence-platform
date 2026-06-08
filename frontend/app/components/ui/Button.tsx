import type { ButtonHTMLAttributes, ReactNode } from "react";

type ButtonVariant = "primary" | "secondary" | "ghost" | "outline" | "danger";
type ButtonSize = "sm" | "md" | "lg" | "icon";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary: "border-transparent bg-[var(--ukip-primary)] text-white shadow-[var(--ukip-glow-violet)] hover:bg-[var(--ukip-primary-strong)]",
  secondary: "border-[var(--ukip-border)] bg-[var(--ukip-panel-strong)] text-[var(--ukip-text)] hover:bg-violet-500/10",
  ghost: "border-transparent bg-transparent text-[var(--ukip-muted)] hover:bg-[var(--ukip-panel-strong)] hover:text-[var(--ukip-text-strong)]",
  outline: "border-[var(--ukip-border)] bg-transparent text-[var(--ukip-text)] hover:border-violet-400/40 hover:bg-[var(--ukip-panel-strong)]",
  danger: "border-transparent bg-[var(--ukip-danger)] text-white hover:brightness-110",
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-xs",
  md: "h-10 px-4 text-sm",
  lg: "h-11 px-5 text-sm",
  icon: "h-10 w-10 p-0",
};

export default function Button({
  children,
  className = "",
  variant = "primary",
  size = "md",
  leftIcon,
  rightIcon,
  type = "button",
  ...props
}: ButtonProps) {
  if (
    process.env.NODE_ENV !== "production" &&
    size === "icon" &&
    !props["aria-label"]?.trim()
  ) {
    throw new Error('Button with size="icon" requires a non-empty aria-label.');
  }

  return (
    <button
      type={type}
      className={`ukip-focus inline-flex items-center justify-center gap-2 rounded-[var(--ukip-radius-md)] border font-semibold transition disabled:pointer-events-none disabled:opacity-50 ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      {...props}
    >
      {leftIcon}
      {children}
      {rightIcon}
    </button>
  );
}
