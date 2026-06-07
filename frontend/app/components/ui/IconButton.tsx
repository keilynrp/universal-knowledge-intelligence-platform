import type { ButtonProps, ButtonVariant } from "./Button";
import Button from "./Button";

export interface IconButtonProps extends Omit<ButtonProps, "size" | "variant" | "leftIcon" | "rightIcon" | "aria-label"> {
  label: string;
  variant?: ButtonVariant;
}

export default function IconButton({
  label,
  variant = "outline",
  className = "",
  children,
  ...props
}: IconButtonProps) {
  return (
    <Button
      aria-label={label}
      title={label}
      size="icon"
      variant={variant}
      className={`rounded-full ${className}`}
      {...props}
    >
      {children}
    </Button>
  );
}

