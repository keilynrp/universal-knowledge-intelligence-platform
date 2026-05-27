"use client";

import { useState } from "react";
import { useLanguage } from "../contexts/LanguageContext";
import { useTheme } from "../contexts/ThemeContext";
import { useAuth } from "../contexts/AuthContext";
import { PageHeader, TabNav, useToast } from "../components/ui";
import PreferencesTab from "./PreferencesTab";
import BrandingTab from "./BrandingTab";
import AccountTab from "./AccountTab";
import NotificationsTab from "./NotificationsTab";
import AuthSettingsTab from "./AuthSettingsTab";
import UsersTab from "./UsersTab";
import WebhooksTab from "./WebhooksTab";
import WorkspaceResetTab from "./WorkspaceResetTab";
import DataFixesTab from "./DataFixesTab";
import FieldCorrespondenceRulesTab from "./FieldCorrespondenceRulesTab";
import AssistantGuardrailsTab from "./AssistantGuardrailsTab";

// ── Types ───────────────────────────────────────────────────────────────────

type Tab = "preferences" | "account" | "users" | "auth" | "webhooks" | "notifications" | "branding" | "workspace_reset" | "field_rules" | "assistant_guardrails" | "data_fixes";


// ── Main Page ────────────────────────────────────────────────────────────────

export default function SettingsPage() {
    const { language, setLanguage, t } = useLanguage();
    const { theme, setTheme } = useTheme();
    const { user, updateAvatarUrl } = useAuth();
    const { toast } = useToast();

    const isSuperAdmin = user?.role === "super_admin";

    const isAdmin = user?.role === "super_admin" || user?.role === "admin";

    const tabs = [
        { id: "preferences", label: t("settings.tab.preferences") },
        { id: "account", label: t("settings.tab.account") },
        ...(isSuperAdmin ? [{ id: "users", label: t("settings.tab.users") }] : []),
        ...(isAdmin ? [{ id: "auth", label: t("settings.tab.auth") }] : []),
        ...(isAdmin ? [{ id: "webhooks", label: t("settings.tab.webhooks") }] : []),
        ...(isAdmin ? [{ id: "notifications", label: t("settings.tab.notifications") }] : []),
        ...(isAdmin ? [{ id: "branding", label: t("settings.tab.branding") }] : []),
        ...(isAdmin ? [{ id: "workspace_reset", label: t("settings.tab.workspace_reset") }] : []),
        ...(isAdmin ? [{ id: "field_rules", label: "Field rules" }] : []),
        ...(isAdmin ? [{ id: "assistant_guardrails", label: "Assistant guardrails" }] : []),
        ...(isSuperAdmin ? [{ id: "data_fixes", label: "Data fixes" }] : []),
    ];

    const [tab, setTab] = useState<Tab>("preferences");

    return (
        <div className="space-y-6">
            <PageHeader
                breadcrumbs={[{ label: t("nav.home"), href: "/" }, { label: t("settings.title") }]}
                title={t("settings.title")}
                description={t("settings.subtitle")}
            />

            <TabNav
                tabs={tabs}
                activeTab={tab}
                onTabChange={(id) => setTab(id as Tab)}
            />

            {tab === "preferences" && (
                <PreferencesTab
                    language={language}
                    setLanguage={setLanguage}
                    theme={theme}
                    setTheme={setTheme}
                    t={t}
                />
            )}
            {tab === "account"        && <AccountTab user={user} updateAvatarUrl={updateAvatarUrl} toast={toast} />}
            {tab === "users"          && isSuperAdmin && <UsersTab currentUserId={user?.id ?? 0} toast={toast} />}
            {tab === "auth"           && isAdmin && <AuthSettingsTab toast={toast} />}
            {tab === "webhooks"       && isAdmin && <WebhooksTab toast={toast} />}
            {tab === "notifications"  && isAdmin && <NotificationsTab toast={toast} />}
            {tab === "branding"       && isAdmin && <BrandingTab toast={toast} />}
            {tab === "workspace_reset" && isAdmin && <WorkspaceResetTab toast={toast} />}
            {tab === "field_rules"     && isAdmin && <FieldCorrespondenceRulesTab toast={toast} />}
            {tab === "assistant_guardrails" && isAdmin && <AssistantGuardrailsTab toast={toast} />}
            {tab === "data_fixes"      && isSuperAdmin && <DataFixesTab toast={toast} />}
        </div>
    );
}
