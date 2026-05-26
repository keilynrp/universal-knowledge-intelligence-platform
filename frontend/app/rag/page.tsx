"use client";

import { PageHeader } from "../components/ui";
import RAGChatInterface from "../components/RAGChatInterface";
import { useAssistantContextRegistration } from "../contexts/AssistantContext";
import { useDomain } from "../contexts/DomainContext";
import { useLanguage } from "../contexts/LanguageContext";

export default function RAGPage() {
    const { t } = useLanguage();
    const { activeDomainId } = useDomain();
    useAssistantContextRegistration({
        route: "/rag",
        domainId: activeDomainId || "all",
        moduleLabel: "RAG semantico",
        recommendedActions: [
            "Consultar evidencia sobre entidades enriquecidas",
            "Reindexar el catalogo si faltan fuentes",
            "Comparar respuesta RAG con contexto del dominio",
        ],
    });

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
