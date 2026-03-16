"use client";

import { PageHeader } from "../components/ui";
import RAGChatInterface from "../components/RAGChatInterface";
import { useLanguage } from "../contexts/LanguageContext";

export default function RAGPage() {
    const { t } = useLanguage();
    return (
        <div className="space-y-6">
            <PageHeader
                breadcrumbs={[{ label: "Home", href: "/" }, { label: t('page.rag.breadcrumb') }]}
                title={t('page.rag.title')}
                description={t('page.rag.description')}
            />
            <RAGChatInterface />
        </div>
    );
}
