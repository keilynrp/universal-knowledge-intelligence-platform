"use client";

import ProvBadge, { type ProvenanceLayer } from "./ProvBadge";

/**
 * ProvenanceFieldSection — Groups entity fields by provenance layer
 * with a visual header badge. Used in entity detail views.
 */

interface ProvenanceFieldSectionProps {
  layer: ProvenanceLayer;
  title: string;
  children: React.ReactNode;
  className?: string;
}

const SECTION_STYLES: Record<ProvenanceLayer, string> = {
  source: "border-l-gray-300 dark:border-l-gray-600",
  enrichment: "border-l-cyan-400 dark:border-l-cyan-500",
  canonical: "border-l-emerald-400 dark:border-l-emerald-500",
  authority: "border-l-violet-400 dark:border-l-violet-500",
};

export default function ProvenanceFieldSection({
  layer,
  title,
  children,
  className = "",
}: ProvenanceFieldSectionProps) {
  return (
    <section
      className={`border-l-2 pl-3 py-2 ${SECTION_STYLES[layer]} ${className}`}
    >
      <div className="flex items-center gap-2 mb-2">
        <ProvBadge layer={layer} size="sm" />
        <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
          {title}
        </h4>
      </div>
      <div className="space-y-1">{children}</div>
    </section>
  );
}
