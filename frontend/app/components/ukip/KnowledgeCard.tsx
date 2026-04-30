import type { ReactNode } from "react";

interface KnowledgeCardProps {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  footer?: ReactNode;
  className?: string;
}

export default function KnowledgeCard({ eyebrow, title, description, footer, className = "" }: KnowledgeCardProps) {
  return (
    <article className={`ukip-panel-soft p-5 ${className}`}>
      {eyebrow ? <p className="ukip-kicker">{eyebrow}</p> : null}
      <h3 className="mt-2 text-base font-semibold text-[var(--ukip-text-strong)]">{title}</h3>
      {description ? <p className="mt-2 text-sm leading-6 text-[var(--ukip-muted)]">{description}</p> : null}
      {footer ? <div className="mt-4 border-t border-[var(--ukip-border)] pt-4">{footer}</div> : null}
    </article>
  );
}

