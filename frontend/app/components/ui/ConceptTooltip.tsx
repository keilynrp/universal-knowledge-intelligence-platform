"use client";

import { useId, useState, type KeyboardEvent, type ReactNode } from "react";
import { useLanguage } from "../../contexts/LanguageContext";
import { CONCEPT_GLOSSARY, type ConceptKey } from "../../lib/conceptGlossary";

interface ConceptTooltipProps {
  concept: ConceptKey;
  children?: ReactNode;
  className?: string;
}

export default function ConceptTooltip({ concept, children, className = "" }: ConceptTooltipProps) {
  const { t } = useLanguage();
  const tooltipId = useId();
  const descriptionId = `${tooltipId}-description`;
  const [open, setOpen] = useState(false);
  const definition = CONCEPT_GLOSSARY[concept];
  const translatedTitle = t(definition.titleKey);
  const translatedBody = t(definition.definitionKey);
  const title = translatedTitle === definition.titleKey ? definition.fallbackTitle : translatedTitle;
  const body = translatedBody === definition.definitionKey ? definition.fallbackDefinition : translatedBody;
  const translatedAria = t("concept.tooltip.open", { concept: title });
  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <span
      className={`relative inline-flex items-center gap-1 ${className}`}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      {children ?? title}
      <button
        type="button"
        aria-label={translatedAria === "concept.tooltip.open" ? `What ${title} means in UKIP` : translatedAria}
        aria-controls={tooltipId}
        aria-describedby={descriptionId}
        aria-expanded={open}
        onBlur={() => setOpen(false)}
        onClick={() => setOpen(true)}
        onFocus={() => setOpen(true)}
        onKeyDown={handleKeyDown}
        className="relative inline-flex h-5 w-5 shrink-0 touch-manipulation items-center justify-center rounded-full text-[var(--ukip-muted)] outline-none transition-colors after:absolute after:-inset-2 hover:bg-violet-500/10 hover:text-violet-500 focus-visible:ring-2 focus-visible:ring-violet-500/70"
      >
        <svg aria-hidden="true" className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <circle cx="12" cy="12" r="9" strokeWidth="1.8" />
          <path strokeLinecap="round" strokeWidth="1.8" d="M12 10.75v5M12 7.5h.01" />
        </svg>
      </button>
      <span id={descriptionId} className="sr-only">
        {title}. {body}
      </span>
      {open ? (
        <span
          id={tooltipId}
          role="tooltip"
          className="absolute left-0 top-full z-50 mt-2 w-80 max-w-[calc(100vw-2rem)] rounded-xl border border-[var(--ukip-border)] bg-[var(--ukip-panel)] p-3 text-left normal-case tracking-normal shadow-xl"
        >
          <span className="block text-xs font-semibold text-[var(--ukip-text-strong)]">{title}</span>
          <span className="mt-1 block text-xs font-normal leading-5 text-[var(--ukip-muted)]">{body}</span>
        </span>
      ) : null}
    </span>
  );
}

export function EntityConcept({
  children,
  className = "",
}: Pick<ConceptTooltipProps, "children" | "className">) {
  return (
    <ConceptTooltip concept="entity" className={className}>
      {children}
    </ConceptTooltip>
  );
}
