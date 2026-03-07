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
    bg: "bg-gray-100 dark:bg-gray-800",
    text: "text-gray-600 dark:text-gray-400",
    dot: "bg-gray-400",
  },
  success: {
    bg: "bg-emerald-50 dark:bg-emerald-500/10",
    text: "text-emerald-700 dark:text-emerald-400",
    dot: "bg-emerald-500",
  },
  warning: {
    bg: "bg-amber-50 dark:bg-amber-500/10",
    text: "text-amber-700 dark:text-amber-400",
    dot: "bg-amber-400",
  },
  error: {
    bg: "bg-red-50 dark:bg-red-500/10",
    text: "text-red-700 dark:text-red-400",
    dot: "bg-red-500",
  },
  info: {
    bg: "bg-blue-50 dark:bg-blue-500/10",
    text: "text-blue-700 dark:text-blue-400",
    dot: "bg-blue-500",
  },
  purple: {
    bg: "bg-violet-50 dark:bg-violet-500/10",
    text: "text-violet-700 dark:text-violet-400",
    dot: "bg-violet-500",
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
            <span className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-75 ${classes.dot}`} />
          )}
          <span className={`relative inline-flex h-1.5 w-1.5 rounded-full ${classes.dot}`} />
        </span>
      )}
      {children}
    </span>
  );
}
