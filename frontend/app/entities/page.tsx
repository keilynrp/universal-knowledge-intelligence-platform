"use client";

import EntityTable from "../components/EntityTable";
import { useLanguage } from "../contexts/LanguageContext";

export default function EntitiesPage() {
  const { t } = useLanguage();
  const tr = (key: string, fallback: string) => {
    const value = t(key);
    return value === key ? fallback : value;
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-[var(--ukip-text-strong)]">
          {tr("page.entity_table.title", "Knowledge Explorer")}
        </h1>
        <p className="mt-1 text-sm text-[var(--ukip-muted)]">
          {tr("page.entity_table.subtitle", "Browse, filter, enrich, and review records in the knowledge base.")}
        </p>
      </div>
      <EntityTable />
    </div>
  );
}
