import type { HTMLAttributes } from "react";

export default function SemanticPanel({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`ukip-gradient-panel relative overflow-hidden p-5 before:pointer-events-none before:absolute before:right-[-5rem] before:top-[-6rem] before:h-56 before:w-56 before:rounded-full before:bg-violet-400/10 before:blur-3xl ${className}`}
      {...props}
    />
  );
}

