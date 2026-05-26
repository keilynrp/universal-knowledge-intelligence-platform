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
        actionLinks: [
            {
                id: "rag-reindex",
                label: "Reindexar RAG",
                href: "/rag",
                kind: "mutation",
                apiPath: "/rag/index",
                method: "POST",
                requiresConfirmation: true,
                confirmationLabel: "Se reconstruira el indice RAG con las entidades enriquecidas disponibles. Puede tardar y requiere rol admin.",
                successLabel: "Indice RAG reconstruido correctamente.",
            },
            { id: "rag-dashboard", label: "Volver al dashboard", href: "/analytics/dashboard", kind: "navigate" },
            { id: "rag-entities", label: "Abrir catalogo interno", href: "/", kind: "navigate" },
            { id: "rag-reports", label: "Convertir respuesta en brief", href: "/reports?preset=pilot-brief", kind: "export", requiresConfirmation: true, confirmationLabel: "Se abrira reportes para convertir hallazgos RAG en un brief." },
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
