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
    bg: "bg-panel-strong",
    text: "text-muted",
    dot: "bg-muted-soft",
  },
  success: {
    bg: "bg-success-soft",
    text: "text-success",
    dot: "bg-success",
  },
  warning: {
    bg: "bg-warning-soft",
    text: "text-warning",
    dot: "bg-warning",
  },
  error: {
    bg: "bg-danger-soft",
    text: "text-danger",
    dot: "bg-danger",
  },
  info: {
    bg: "bg-info-soft",
    text: "text-info",
    dot: "bg-info",
  },
  purple: {
    bg: "bg-primary-soft",
    text: "text-violet",
    dot: "bg-violet",
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
