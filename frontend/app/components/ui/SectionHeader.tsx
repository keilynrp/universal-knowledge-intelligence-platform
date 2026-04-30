import type { ReactNode } from "react";

interface SectionHeaderProps {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
}

export default function SectionHeader({ eyebrow, title, description, actions, className = "" }: SectionHeaderProps) {
  return (
    <div className={`flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between ${className}`}>
      <div className="min-w-0">
        {eyebrow ? <p className="ukip-kicker">{eyebrow}</p> : null}
        <h2 className="mt-1 text-lg font-semibold text-[var(--ukip-text-strong)]">{title}</h2>
        {description ? <p className="mt-1 text-sm leading-6 text-[var(--ukip-muted)]">{description}</p> : null}
      </div>
      {actions ? <div className="shrink-0">{actions}</div> : null}
    </div>
  );
}

