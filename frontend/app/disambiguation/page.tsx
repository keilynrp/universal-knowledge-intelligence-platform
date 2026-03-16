"use client";

import { PageHeader } from "../components/ui";
import DisambiguationTool from "../components/DisambiguationTool";
import { useLanguage } from "../contexts/LanguageContext";

export default function DisambiguationPage() {
  const { t } = useLanguage();
  return (
    <div className="space-y-6">
      <PageHeader
        breadcrumbs={[{ label: "Home", href: "/" }, { label: t('page.disambiguation.breadcrumb') }]}
        title={t('page.disambiguation.title')}
        description={t('page.disambiguation.description')}
      />
      <DisambiguationTool />
    </div>
  );
}
