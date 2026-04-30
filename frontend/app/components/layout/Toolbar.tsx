import type { HTMLAttributes } from "react";

export default function Toolbar({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`flex flex-col gap-3 rounded-[var(--ukip-radius-xl)] border border-[var(--ukip-border)] bg-[var(--ukip-panel)] p-3 backdrop-blur sm:flex-row sm:items-center sm:justify-between ${className}`}
      {...props}
    />
  );
}
