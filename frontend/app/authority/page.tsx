"use client";

import { useState } from "react";
import { PageHeader, TabNav } from "../components/ui";
import PilotFlowCard from "../components/PilotFlowCard";
import { useAssistantContextRegistration } from "../contexts/AssistantContext";
import { useDomain } from "../contexts/DomainContext";
import { useLanguage } from "../contexts/LanguageContext";
import DisambiguationTab from "./DisambiguationTab";
import ReviewQueueTab from "./ReviewQueueTab";

export default function AuthorityPage() {
    const { activeDomain } = useDomain();
    const { t } = useLanguage();
    const [tab, setTab] = useState<"disambiguation" | "review">("disambiguation");
    useAssistantContextRegistration({
        route: "/authority",
        domainId: activeDomain?.id || "all",
        moduleLabel: tab === "disambiguation" ? "Control de autoridad" : "Cola de revision",
        recommendedActions: [
            tab === "disambiguation" ? "Explicar posibles colisiones de valores" : "Priorizar sugerencias pendientes",
            "Crear reglas solo con evidencia suficiente",
            "Revisar falsos positivos antes de confirmar en lote",
        ],
    });

    const tabs = [
        { id: "disambiguation" as const, label: t("page.authority.tab_groups") },
        { id: "review" as const, label: t("page.authority.tab_review_queue") },
    ];

    return (
        <div className="space-y-6">
            <PageHeader
                breadcrumbs={[{ label: "Home", href: "/" }, { label: t("page.authority.breadcrumb") }]}
                title={t("page.authority.title")}
                description={t("page.authority.description")}
            />

            <PilotFlowCard
                currentStep="review"
                tone="amber"
                title={t("page.authority.guided.title")}
                body={tab === "disambiguation"
                    ? t("page.authority.guided.disambiguation")
                    : t("page.authority.guided.review")}
                primaryCta={{
                    href: "/reports?preset=pilot-brief",
                    label: t("page.authority.guided.cta_reports"),
                }}
                secondaryCta={{
                    href: "/analytics/dashboard",
                    label: t("page.authority.guided.cta_dashboard"),
                }}
            />

            <TabNav
                tabs={tabs}
                activeTab={tab}
                onTabChange={(id) => setTab(id as "disambiguation" | "review")}
            />

            {tab === "disambiguation" && <DisambiguationTab activeDomain={activeDomain} />}
            {tab === "review" && <ReviewQueueTab activeDomain={activeDomain} />}
        </div>
    );
}
