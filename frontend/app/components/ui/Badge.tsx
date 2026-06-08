"use client";

type BadgeVariant = "default" | "success" | "warning" | "error" | "info" | "purple";

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  dot?: boolean;
  dotPulse?: boolean;
  size?: "sm" | "md";
}

const VARIANT_CLASSES: Record<BadgeVariant, { bg: string; text: string; dot: string }> = {
  default: {
    bg: "bg-[var(--ukip-panel-strong)]",
    text: "text-[var(--ukip-muted)]",
    dot: "bg-[var(--ukip-muted-soft)]",
  },
  success: {
    bg: "bg-[var(--ukip-success-soft)]",
    text: "text-[var(--ukip-success)]",
    dot: "bg-[var(--ukip-success)]",
  },
  warning: {
    bg: "bg-[var(--ukip-warning-soft)]",
    text: "text-[var(--ukip-warning)]",
    dot: "bg-[var(--ukip-warning)]",
  },
  error: {
    bg: "bg-[var(--ukip-danger-soft)]",
    text: "text-[var(--ukip-danger)]",
    dot: "bg-[var(--ukip-danger)]",
  },
  info: {
    bg: "bg-[var(--ukip-info-soft)]",
    text: "text-[var(--ukip-info)]",
    dot: "bg-[var(--ukip-info)]",
  },
  purple: {
    bg: "bg-[var(--ukip-primary-soft)]",
    text: "text-[var(--ukip-violet)]",
    dot: "bg-[var(--ukip-violet)]",
  },
};

export default function Badge({ children, variant = "default", dot, dotPulse, size = "sm" }: BadgeProps) {
  const classes = VARIANT_CLASSES[variant];
  const sizeClasses = size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-sm";

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full font-medium ${sizeClasses} ${classes.bg} ${classes.text}`}>
      {dot && (
        <span className="relative flex h-1.5 w-1.5">
          {dotPulse && (
            <span
              data-testid="badge-dot-pulse"
              className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-75 ${classes.dot}`}
            />
          )}
          <span
            data-testid="badge-dot"
            className={`relative inline-flex h-1.5 w-1.5 rounded-full ${classes.dot}`}
          />
        </span>
      )}
      {children}
    </span>
  );
}
