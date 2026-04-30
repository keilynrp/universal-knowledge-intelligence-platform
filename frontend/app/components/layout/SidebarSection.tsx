import type { ReactNode } from "react";

interface SidebarSectionProps {
  title?: ReactNode;
  children: ReactNode;
  compact?: boolean;
  className?: string;
}

export default function SidebarSection({ title, children, compact = false, className = "" }: SidebarSectionProps) {
  return (
    <section className={className}>
      {title && !compact ? (
        <div className="mb-2 px-3">
          <span className="text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--ukip-muted-soft)]">
            {title}
          </span>
        </div>
      ) : null}
      {children}
    </section>
  );
}

