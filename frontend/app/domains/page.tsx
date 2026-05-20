"use client";

import { useState, useEffect } from "react";
import { PageHeader, Badge } from "../components/ui";
import { useDomain, DomainAttribute, Paradigm } from "../contexts/DomainContext";
import { useAuth } from "../contexts/AuthContext";
import { apiFetch } from "@/lib/api";
import { useFocusTrap } from "../hooks/useFocusTrap";
import { useLanguage } from "../contexts/LanguageContext";

const BUILTIN_IDS = new Set(["default", "science", "healthcare"]);
const ALL_DOMAINS_ID = "all";
const ALL_DOMAINS_LABEL = "Todos los dominios";

const ICON_OPTIONS = ["Database", "Microscope", "Heart", "Building", "BookOpen", "Globe", "Briefcase", "FlaskConical"];

function DomainIcon({ icon }: { icon?: string | null }) {
  switch (icon) {
    case "Microscope":
      return <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" /></svg>;
    case "Heart":
      return <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z" /></svg>;
    case "Building":
      return <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.25 21h19.5m-18-18v18m10.5-18v18m6-13.5V21M6.75 6.75h.75m-.75 3h.75m-.75 3h.75m3-6h.75m-.75 3h.75m-.75 3h.75M6.75 21v-3.375c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21M3 3h12m-.75 4.5H21m-3.75 3.75h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008z" /></svg>;
    case "BookOpen":
      return <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" /></svg>;
    case "Globe":
      return <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418" /></svg>;
    case "Briefcase":
      return <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20.25 14.15v4.25c0 1.094-.787 2.036-1.872 2.18-2.087.277-4.216.42-6.378.42s-4.291-.143-6.378-.42c-1.085-.144-1.872-1.086-1.872-2.18v-4.25m16.5 0a2.18 2.18 0 00.75-1.661V8.706c0-1.081-.768-2.015-1.837-2.175a48.114 48.114 0 00-3.413-.387m4.5 8.006c-.194.165-.42.295-.673.38A23.978 23.978 0 0112 15.75c-2.648 0-5.195-.429-7.577-1.22a2.016 2.016 0 01-.673-.38m0 0A2.18 2.18 0 013 12.489V8.706c0-1.081.768-2.015 1.837-2.175a48.111 48.111 0 013.413-.387m7.5 0V5.25A2.25 2.25 0 0013.5 3h-3a2.25 2.25 0 00-2.25 2.25v.894m7.5 0a48.667 48.667 0 00-7.5 0M12 12.75h.008v.008H12v-.008z" /></svg>;
    case "FlaskConical":
      return <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5" /></svg>;
    default: // Database
      return <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" /></svg>;
  }
}

type NewAttr = { name: string; label: string; type: string; required: boolean; is_core: boolean };
const emptyAttr = (): NewAttr => ({ name: "", label: "", type: "string", required: false, is_core: false });

type ParadigmForm = {
  id: string;
  label: string;
  description: string;
  terms: string;          // comma-separated
  document_types: string; // comma-separated
  journals_affinity: string; // comma-separated
};
const emptyParadigm = (): ParadigmForm => ({
  id: "", label: "", description: "", terms: "", document_types: "", journals_affinity: "",
});

const SLUG_RE = /^[a-z][a-z0-9_]*$/;
const PARADIGM_ID_RE = /^[a-z][a-z0-9_]*$/;

function splitCSV(s: string): string[] {
  return s.split(",").map(t => t.trim()).filter(Boolean);
}

export default function DomainsPage() {
  const { domains, activeDomainId, setActiveDomainId, refreshDomains } = useDomain();
  const { user } = useAuth();
  const { t } = useLanguage();
  const isAdmin = user?.role === "super_admin" || user?.role === "admin";
  const tr = (key: string, fallback: string, params?: Record<string, string | number>) => {
    const value = t(key, params);
    return value === key ? fallback : value;
  };

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "ok" | "err"; msg: string } | null>(null);

  // Domain detail tabs
  const [detailTab, setDetailTab] = useState<"attributes" | "epistemic">("attributes");

  // Epistemic config state
  const [paradigms, setParadigms] = useState<ParadigmForm[]>([]);
  const [savingEpistemic, setSavingEpistemic] = useState(false);
  const [expandedParadigm, setExpandedParadigm] = useState<number | null>(null);

  // New domain form state
  const [formId, setFormId] = useState("");
  const [formName, setFormName] = useState("");
  const [formDesc, setFormDesc] = useState("");
  const [formEntity, setFormEntity] = useState("");
  const [formIcon, setFormIcon] = useState("Database");
  const [formAttrs, setFormAttrs] = useState<NewAttr[]>([emptyAttr()]);

  const slideOverRef = useFocusTrap<HTMLDivElement>(showForm);

  const selectedDomain = domains.find(d => d.id === selectedId) ?? null;
  const activeDomainLabel = activeDomainId === ALL_DOMAINS_ID ? ALL_DOMAINS_LABEL : activeDomainId ?? "—";

  // Initialize epistemic form when selected domain changes
  useEffect(() => {
    setDetailTab("attributes");
    setExpandedParadigm(null);
    if (!selectedId) { setParadigms([]); return; }
    const d = domains.find(x => x.id === selectedId);
    const ep = d?.epistemology;
    if (ep?.paradigms?.length) {
      setParadigms(ep.paradigms.map((p: Paradigm) => ({
        id: p.id,
        label: p.label,
        description: p.description ?? "",
        terms: (p.indicators?.terms ?? []).join(", "),
        document_types: (p.indicators?.document_types ?? []).join(", "),
        journals_affinity: (p.indicators?.journals_affinity ?? []).join(", "),
      })));
    } else {
      setParadigms([]);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  const handleSaveEpistemic = async () => {
    if (!selectedId) return;
    // Validate paradigm IDs
    for (const p of paradigms) {
      if (!PARADIGM_ID_RE.test(p.id)) {
        flash("err", `ID de paradigma inválido: "${p.id}". Use solo letras minúsculas, números y guión bajo.`);
        return;
      }
      if (!p.label.trim()) {
        flash("err", `El paradigma "${p.id}" necesita un nombre.`);
        return;
      }
    }
    const ids = paradigms.map(p => p.id);
    if (new Set(ids).size !== ids.length) {
      flash("err", "Hay IDs de paradigma duplicados.");
      return;
    }

    setSavingEpistemic(true);
    try {
      const body = {
        paradigms: paradigms.map(p => ({
          id: p.id,
          label: p.label,
          description: p.description,
          indicators: {
            terms: splitCSV(p.terms),
            document_types: splitCSV(p.document_types),
            journals_affinity: splitCSV(p.journals_affinity),
          },
        })),
        evidence_hierarchy: [],
      };
      const res = await apiFetch(`/domains/${selectedId}/epistemology`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Error desconocido" }));
        flash("err", err.detail ?? "Error al guardar la configuración epistémica");
      } else {
        await refreshDomains();
        flash("ok", paradigms.length === 0
          ? "Análisis epistémico desactivado para este dominio."
          : `Configuración epistémica guardada (${paradigms.length} paradigma${paradigms.length !== 1 ? "s" : ""}).`);
      }
    } catch {
      flash("err", "Error de red al guardar la configuración epistémica");
    } finally {
      setSavingEpistemic(false);
    }
  };

  const updateParadigm = (i: number, field: keyof ParadigmForm, value: string) => {
    setParadigms(prev => prev.map((p, idx) => idx === i ? { ...p, [field]: value } : p));
  };

  const getIconLabel = (icon: string) => t(`page.domains.icon.${icon}`);

  const flash = (type: "ok" | "err", msg: string) => {
    setFeedback({ type, msg });
    setTimeout(() => setFeedback(null), 4000);
  };

  const resetForm = () => {
    setFormId(""); setFormName(""); setFormDesc(""); setFormEntity("");
    setFormIcon("Database"); setFormAttrs([emptyAttr()]);
  };

  const handleCreate = async () => {
    if (!SLUG_RE.test(formId)) { flash("err", t("page.domains.error_invalid_id")); return; }
    if (!formName.trim() || !formDesc.trim() || !formEntity.trim()) { flash("err", t("page.domains.error_required_fields")); return; }
    const invalid = formAttrs.find(a => !SLUG_RE.test(a.name) || !a.label.trim());
    if (invalid) { flash("err", t("page.domains.error_invalid_attribute", { name: invalid.name || t("page.domains.empty_field_fallback") })); return; }

    setSaving(true);
    try {
      const res = await apiFetch("/domains", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: formId, name: formName, description: formDesc, primary_entity: formEntity, icon: formIcon, attributes: formAttrs }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: t("page.domains.error_unknown") }));
        flash("err", err.detail ?? t("page.domains.error_create_failed"));
      } else {
        await refreshDomains();
        flash("ok", t("page.domains.success_created", { name: formName }));
        setShowForm(false);
        resetForm();
        setSelectedId(formId);
      }
    } catch {
      flash("err", t("page.domains.error_network"));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (domainId: string) => {
    if (!confirm(t("page.domains.delete_confirm", { id: domainId }))) return;
    setDeleting(domainId);
    try {
      const res = await apiFetch(`/domains/${domainId}`, { method: "DELETE" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: t("page.domains.error_unknown") }));
        flash("err", err.detail ?? t("page.domains.error_delete_failed"));
      } else {
        await refreshDomains();
        flash("ok", t("page.domains.success_deleted", { id: domainId }));
        if (selectedId === domainId) setSelectedId(null);
      }
    } catch {
      flash("err", t("page.domains.error_network"));
    } finally {
      setDeleting(null);
    }
  };

  const updateAttr = (i: number, field: keyof NewAttr, value: string | boolean) => {
    setFormAttrs(prev => prev.map((a, idx) => idx === i ? { ...a, [field]: value } : a));
  };

  return (
    <div className="flex h-full flex-col gap-6">
      <PageHeader
        breadcrumbs={[{ label: t("nav.home"), href: "/" }, { label: t('page.domains.breadcrumb') }]}
        title={t('page.domains.title')}
        description={t("page.domains.description", { count: domains.length, active: activeDomainLabel })}
        actions={isAdmin ? (
          <button
            onClick={() => { setShowForm(true); resetForm(); }}
            className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>
            {t('page.domains.new_button')}
          </button>
        ) : undefined}
      />

      {/* Feedback banner */}
      {feedback && (
        <div className={`rounded-lg px-4 py-3 text-sm font-medium ${feedback.type === "ok" ? "bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400" : "bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400"}`}>
          {feedback.msg}
        </div>
      )}

      {/* Main layout */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3 md:gap-6 flex-1 min-h-0">
        {/* Domain list */}
        <div className="flex flex-col gap-3 overflow-y-auto">
          <div
            onClick={() => setSelectedId(null)}
            onKeyDown={e => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                setSelectedId(null);
              }
            }}
            role="button"
            tabIndex={0}
            aria-pressed={selectedId === null}
            className={`w-full text-left rounded-xl border p-4 transition-all ${
              selectedId === null
                ? "border-violet-500 bg-violet-50 ring-1 ring-violet-500 dark:bg-violet-900/10"
                : "border-gray-200 bg-white shadow-sm hover:border-gray-300 dark:border-gray-800 dark:bg-gray-900 dark:hover:border-gray-700"
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex min-w-0 items-center gap-3">
                <div className={`flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg ${
                  activeDomainId === ALL_DOMAINS_ID
                    ? "bg-violet-100 text-violet-600 dark:bg-violet-600/20 dark:text-violet-300"
                    : "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400"
                }`}>
                  <DomainIcon icon="Globe" />
                </div>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="truncate text-sm font-medium text-gray-900 dark:text-white">{ALL_DOMAINS_LABEL}</span>
                    <Badge variant="purple" dot>{tr("page.domains.default_badge", "Default")}</Badge>
                    {activeDomainId === ALL_DOMAINS_ID && (
                      <Badge variant="info" dot>{t("page.domains.active_badge")}</Badge>
                    )}
                  </div>
                  <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                    {t("page.domains.all_domains_meta", { count: domains.length }) === "page.domains.all_domains_meta"
                      ? `${domains.length} dominios activos agregados`
                      : t("page.domains.all_domains_meta", { count: domains.length })}
                  </p>
                </div>
              </div>
            </div>
            <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
              {t("page.domains.all_domains_description") === "page.domains.all_domains_description"
                ? "Clasificación por defecto que suma los registros e ingestas activas de todos los dominios."
                : t("page.domains.all_domains_description")}
            </p>
            <div className="mt-3">
              {activeDomainId !== ALL_DOMAINS_ID && (
                <button
                  onClick={e => { e.stopPropagation(); setActiveDomainId(ALL_DOMAINS_ID); }}
                  className="rounded-md bg-violet-100 px-2.5 py-1 text-xs font-medium text-violet-700 transition-colors hover:bg-violet-200 dark:bg-violet-900/30 dark:text-violet-300 dark:hover:bg-violet-900/50"
                >
                  {tr("page.domains.set_default_scope", "Usar sumatoria por defecto")}
                </button>
              )}
            </div>
          </div>
          {domains.map(d => (
            <div
              key={d.id}
              onClick={() => setSelectedId(d.id)}
              onKeyDown={e => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setSelectedId(d.id);
                }
              }}
              role="button"
              tabIndex={0}
              aria-pressed={selectedId === d.id}
              className={`w-full text-left rounded-xl border p-4 transition-all ${
                selectedId === d.id
                  ? "border-blue-500 bg-blue-50 dark:bg-blue-900/10 ring-1 ring-blue-500"
                  : "border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900 hover:border-gray-300 dark:hover:border-gray-700"
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-3 min-w-0">
                  <div className={`flex-shrink-0 flex h-9 w-9 items-center justify-center rounded-lg ${
                    selectedId === d.id ? "bg-blue-100 text-blue-600 dark:bg-blue-600/20 dark:text-blue-400" : "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400"
                  }`}>
                    <DomainIcon icon={d.icon} />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-sm text-gray-900 dark:text-white truncate">{d.name}</span>
                      {activeDomainId === d.id && (
                        <Badge variant="info" dot>{t("page.domains.active_badge")}</Badge>
                      )}
                      {BUILTIN_IDS.has(d.id) && (
                        <Badge variant="default">{t("page.domains.builtin_badge")}</Badge>
                      )}
                    </div>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 truncate">{t("page.domains.domain_card_meta", { entity: d.primary_entity, count: d.attributes.length })}</p>
                  </div>
                </div>
              </div>
              <p className="mt-2 text-xs text-gray-500 dark:text-gray-400 line-clamp-2">{d.description}</p>
              <div className="mt-3 flex items-center gap-2">
                {activeDomainId !== d.id && (
                  <button
                    onClick={e => { e.stopPropagation(); setActiveDomainId(d.id); }}
                    className="rounded-md bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-700 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700 transition-colors"
                  >
                    {t('page.domains.set_active_button')}
                  </button>
                )}
                {isAdmin && !BUILTIN_IDS.has(d.id) && (
                  <button
                    onClick={e => { e.stopPropagation(); handleDelete(d.id); }}
                    disabled={deleting === d.id}
                    className="rounded-md bg-red-50 px-2.5 py-1 text-xs font-medium text-red-600 hover:bg-red-100 dark:bg-red-900/20 dark:text-red-400 dark:hover:bg-red-900/40 transition-colors disabled:opacity-50"
                  >
                    {deleting === d.id ? t('page.domains.deleting') : t('page.domains.delete_button')}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Detail panel */}
        <div className="col-span-2 rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900 overflow-hidden flex flex-col">
          {selectedDomain ? (
            <>
              {/* Panel header */}
              <div className="flex items-center gap-3 border-b border-gray-200 dark:border-gray-800 px-6 py-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 text-blue-600 dark:bg-blue-600/20 dark:text-blue-400">
                  <DomainIcon icon={selectedDomain.icon} />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-gray-900 dark:text-white">{selectedDomain.name}</h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {t("page.domains.primary_entity_label")} <span className="font-medium">{selectedDomain.primary_entity}</span>
                    <span className="mx-2">·</span>
                    {t("page.domains.attributes_count", { count: selectedDomain.attributes.length })}
                  </p>
                </div>
              </div>

              {/* Tabs — epistemic tab only visible to admins */}
              <div className="flex border-b border-gray-200 dark:border-gray-800 px-4">
                <button
                  onClick={() => setDetailTab("attributes")}
                  className={`px-4 py-2.5 text-xs font-medium border-b-2 transition-colors ${
                    detailTab === "attributes"
                      ? "border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400"
                      : "border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300"
                  }`}
                >
                  Atributos
                </button>
                {isAdmin && (
                  <button
                    onClick={() => setDetailTab("epistemic")}
                    className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-medium border-b-2 transition-colors ${
                      detailTab === "epistemic"
                        ? "border-violet-600 text-violet-600 dark:border-violet-400 dark:text-violet-400"
                        : "border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300"
                    }`}
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                    Análisis Epistémico
                    {paradigms.length > 0 && (
                      <span className="rounded-full bg-violet-100 px-1.5 py-0.5 text-xs font-semibold text-violet-700 dark:bg-violet-900/30 dark:text-violet-300">
                        {paradigms.length}
                      </span>
                    )}
                  </button>
                )}
              </div>

              {/* Tab content */}
              {detailTab === "attributes" ? (
                <div className="overflow-y-auto flex-1">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 dark:bg-gray-800/50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">{t('page.domains.table_field_name_header')}</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">{t('page.domains.table_label_header')}</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">{t('page.domains.table_type_header')}</th>
                        <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">{t('page.domains.table_required_header')}</th>
                        <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">{t("page.domains.table_core_header")}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                      {selectedDomain.attributes.map((attr: DomainAttribute) => (
                        <tr key={attr.name} className="hover:bg-gray-50 dark:hover:bg-gray-800/30 transition-colors">
                          <td className="px-6 py-3 font-mono text-xs text-gray-700 dark:text-gray-300">{attr.name}</td>
                          <td className="px-4 py-3 text-gray-700 dark:text-gray-300">{attr.label}</td>
                          <td className="px-4 py-3">
                            <Badge variant={
                              attr.type === "string"  ? "info" :
                              attr.type === "integer" ? "purple" :
                              attr.type === "float"   ? "warning" :
                              attr.type === "boolean" ? "success" :
                              attr.type === "array"   ? "error" : "default"
                            }>
                              {attr.type}
                            </Badge>
                          </td>
                          <td className="px-4 py-3 text-center">
                            {attr.required
                              ? <span className="text-green-500 dark:text-green-400 font-bold">✓</span>
                              : <span className="text-gray-300 dark:text-gray-600">–</span>}
                          </td>
                          <td className="px-4 py-3 text-center">
                            {attr.is_core
                              ? <Badge variant="info">{t("page.domains.core_badge")}</Badge>
                              : <span className="text-gray-300 dark:text-gray-600">–</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                /* ── Epistemic configuration panel ── */
                <div className="flex flex-col flex-1 overflow-hidden">
                  <div className="overflow-y-auto flex-1 px-6 py-5 space-y-4">
                    {/* Status banner */}
                    <div className={`flex items-start gap-3 rounded-lg px-4 py-3 text-sm ${
                      paradigms.length > 0
                        ? "bg-violet-50 text-violet-800 dark:bg-violet-900/20 dark:text-violet-300"
                        : "bg-gray-50 text-gray-600 dark:bg-gray-800/50 dark:text-gray-400"
                    }`}>
                      <svg className="w-4 h-4 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      <span>
                        {paradigms.length > 0
                          ? `Análisis epistémico activo con ${paradigms.length} paradigma${paradigms.length !== 1 ? "s" : ""}. Los registros enriquecidos se clasificarán automáticamente.`
                          : "Sin paradigmas configurados. El análisis epistémico está desactivado para este dominio. Agrega al menos un paradigma para activarlo."}
                      </span>
                    </div>

                    {/* Paradigm list */}
                    {paradigms.map((p, i) => (
                      <div key={i} className="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
                        {/* Paradigm header */}
                        <div
                          className="flex items-center justify-between px-4 py-3 bg-gray-50 dark:bg-gray-800/40 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800/70 transition-colors"
                          onClick={() => setExpandedParadigm(expandedParadigm === i ? null : i)}
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            <svg className={`w-4 h-4 text-gray-400 flex-shrink-0 transition-transform ${expandedParadigm === i ? "rotate-90" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                            </svg>
                            <span className="font-medium text-sm text-gray-900 dark:text-white truncate">
                              {p.label || <span className="text-gray-400 italic">Sin nombre</span>}
                            </span>
                            <span className="font-mono text-xs text-gray-400 dark:text-gray-500 truncate">{p.id}</span>
                            {p.terms && (
                              <span className="rounded-full bg-blue-100 px-1.5 py-0.5 text-xs text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 flex-shrink-0">
                                {splitCSV(p.terms).length} términos
                              </span>
                            )}
                          </div>
                          <button
                            onClick={e => { e.stopPropagation(); setParadigms(prev => prev.filter((_, idx) => idx !== i)); if (expandedParadigm === i) setExpandedParadigm(null); }}
                            className="ml-2 flex-shrink-0 rounded p-1 text-gray-400 hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-900/20 transition-colors"
                            aria-label="Eliminar paradigma"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                          </button>
                        </div>

                        {/* Paradigm form (expanded) */}
                        {expandedParadigm === i && (
                          <div className="px-4 py-4 space-y-3 border-t border-gray-200 dark:border-gray-700">
                            <div className="grid grid-cols-2 gap-3">
                              <div>
                                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                                  ID <span className="text-red-500">*</span>
                                  <span className="ml-1 text-gray-400 font-normal">(slug, ej: empiricist)</span>
                                </label>
                                <input
                                  value={p.id}
                                  onChange={e => updateParadigm(i, "id", e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ""))}
                                  placeholder="empiricist"
                                  className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-mono dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
                                />
                              </div>
                              <div>
                                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Nombre <span className="text-red-500">*</span></label>
                                <input
                                  value={p.label}
                                  onChange={e => updateParadigm(i, "label", e.target.value)}
                                  placeholder="Empiricista / Positivista"
                                  className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-xs dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
                                />
                              </div>
                            </div>
                            <div>
                              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Descripción</label>
                              <input
                                value={p.description}
                                onChange={e => updateParadigm(i, "description", e.target.value)}
                                placeholder="Investigación basada en evidencia empírica y métodos cuantitativos"
                                className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-xs dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
                              />
                            </div>
                            <div>
                              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                                Términos indicadores
                                <span className="ml-1 text-gray-400 font-normal">(separados por coma)</span>
                              </label>
                              <textarea
                                value={p.terms}
                                onChange={e => updateParadigm(i, "terms", e.target.value)}
                                placeholder="randomized controlled trial, p-value, statistical significance, regression, meta-analysis"
                                rows={2}
                                className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-xs dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-violet-500 resize-none"
                              />
                              {p.terms && (
                                <p className="mt-0.5 text-xs text-gray-400">{splitCSV(p.terms).length} términos</p>
                              )}
                            </div>
                            <div>
                              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                                Tipos de documento
                                <span className="ml-1 text-gray-400 font-normal">(separados por coma)</span>
                              </label>
                              <textarea
                                value={p.document_types}
                                onChange={e => updateParadigm(i, "document_types", e.target.value)}
                                placeholder="randomized controlled trial, systematic review, meta-analysis"
                                rows={2}
                                className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-xs dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-violet-500 resize-none"
                              />
                            </div>
                            <div>
                              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                                Journals de afinidad
                                <span className="ml-1 text-gray-400 font-normal">(separados por coma)</span>
                              </label>
                              <textarea
                                value={p.journals_affinity}
                                onChange={e => updateParadigm(i, "journals_affinity", e.target.value)}
                                placeholder="Nature, Science, The Lancet, NEJM"
                                rows={2}
                                className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-xs dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-violet-500 resize-none"
                              />
                            </div>
                          </div>
                        )}
                      </div>
                    ))}

                    {/* Add paradigm button */}
                    <button
                      onClick={() => {
                        const newIdx = paradigms.length;
                        setParadigms(prev => [...prev, emptyParadigm()]);
                        setExpandedParadigm(newIdx);
                      }}
                      className="flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-gray-300 px-4 py-3 text-sm text-gray-500 hover:border-violet-400 hover:text-violet-600 dark:border-gray-700 dark:hover:border-violet-500 dark:hover:text-violet-400 transition-colors"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>
                      Agregar paradigma
                    </button>
                  </div>

                  {/* Footer with save/disable actions */}
                  <div className="flex items-center justify-between border-t border-gray-200 dark:border-gray-800 px-6 py-3">
                    {paradigms.length > 0 && (
                      <button
                        onClick={() => { if (confirm("¿Desactivar el análisis epistémico para este dominio?")) setParadigms([]); }}
                        className="text-xs text-gray-400 hover:text-red-500 dark:hover:text-red-400 transition-colors"
                      >
                        Desactivar análisis epistémico
                      </button>
                    )}
                    <div className="flex items-center gap-3 ml-auto">
                      <span className="text-xs text-gray-400">
                        {paradigms.length === 0 ? "Sin paradigmas — se desactivará" : `${paradigms.length} paradigma${paradigms.length !== 1 ? "s" : ""} configurado${paradigms.length !== 1 ? "s" : ""}`}
                      </span>
                      <button
                        onClick={handleSaveEpistemic}
                        disabled={savingEpistemic}
                        className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50 transition-colors"
                      >
                        {savingEpistemic ? "Guardando…" : "Guardar configuración"}
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 text-gray-400 dark:text-gray-600">
              <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" /></svg>
              <p className="text-sm">{t('page.domains.select_domain_prompt')}</p>
            </div>
          )}
        </div>
      </div>

      {/* New Domain slide-over */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-start justify-end">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setShowForm(false)} aria-hidden="true" />
          <div
            ref={slideOverRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="new-domain-title"
            className="relative z-10 flex h-full w-full max-w-xl flex-col bg-white shadow-2xl dark:bg-gray-950 overflow-y-auto"
          >
            {/* Form header */}
            <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4 dark:border-gray-800">
              <h3 id="new-domain-title" className="font-semibold text-gray-900 dark:text-white">{t('page.domains.form_title')}</h3>
              <button onClick={() => setShowForm(false)} aria-label={t("page.domains.close_button_aria")} className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800">
                <svg className="w-5 h-5" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>

            <div className="flex-1 space-y-5 px-6 py-5">
              {/* Basic info */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label htmlFor="domain-id" className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{t('page.domains.form_id_label')} <span className="text-red-500" aria-label={t("page.domains.required_aria")}>*</span></label>
                  <input
                    id="domain-id"
                    value={formId} onChange={e => setFormId(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ""))}
                    placeholder={t("page.domains.form_id_placeholder")}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <p className="mt-1 text-xs text-gray-400">{t("page.domains.form_id_help")}</p>
                </div>
                <div>
                  <label htmlFor="domain-name" className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{t('page.domains.form_name_label')} <span className="text-red-500" aria-label={t("page.domains.required_aria")}>*</span></label>
                  <input
                    id="domain-name"
                    value={formName} onChange={e => setFormName(e.target.value)}
                    placeholder={t("page.domains.form_name_placeholder")}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="domain-desc" className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{t('page.domains.form_description_label')} <span className="text-red-500" aria-label={t("page.domains.required_aria")}>*</span></label>
                <input
                  id="domain-desc"
                  value={formDesc} onChange={e => setFormDesc(e.target.value)}
                  placeholder={t("page.domains.form_description_placeholder")}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label htmlFor="domain-entity" className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{t("page.domains.form_entity_label")} <span className="text-red-500" aria-label={t("page.domains.required_aria")}>*</span></label>
                  <input
                    id="domain-entity"
                    value={formEntity} onChange={e => setFormEntity(e.target.value)}
                    placeholder={t("page.domains.form_entity_placeholder")}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label htmlFor="domain-icon" className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{t("page.domains.form_icon_label")}</label>
                  <select
                    id="domain-icon"
                    value={formIcon} onChange={e => setFormIcon(e.target.value)}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {ICON_OPTIONS.map(ico => <option key={ico} value={ico}>{getIconLabel(ico)}</option>)}
                  </select>
                </div>
              </div>

              {/* Attributes */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-gray-700 dark:text-gray-300">{t("page.domains.form_attributes_label")} <span className="text-red-500" aria-label={t("page.domains.required_aria")}>*</span></span>
                  <button
                    onClick={() => setFormAttrs(p => [...p, emptyAttr()])}
                    className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:underline"
                  >
                    <svg className="w-3 h-3" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>
                    {t('page.domains.add_attribute_button')}
                  </button>
                </div>
                <div className="space-y-2">
                  {formAttrs.map((attr, i) => (
                    <div key={i} className="grid grid-cols-12 gap-2 items-center">
                      <input
                        value={attr.name} onChange={e => updateAttr(i, "name", e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ""))}
                        placeholder={t("page.domains.attribute_name_placeholder")}
                        aria-label={t("page.domains.attribute_name_aria", { index: i + 1 })}
                        className="col-span-3 rounded-lg border border-gray-300 px-2 py-1.5 text-xs font-mono dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                      />
                      <input
                        value={attr.label} onChange={e => updateAttr(i, "label", e.target.value)}
                        placeholder={t("page.domains.attribute_label_placeholder")}
                        aria-label={t("page.domains.attribute_label_aria", { index: i + 1 })}
                        className="col-span-4 rounded-lg border border-gray-300 px-2 py-1.5 text-xs dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                      />
                      <select
                        value={attr.type} onChange={e => updateAttr(i, "type", e.target.value)}
                        aria-label={t("page.domains.attribute_type_aria", { index: i + 1 })}
                        className="col-span-2 rounded-lg border border-gray-300 px-2 py-1.5 text-xs dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                      >
                        {["string","integer","float","boolean","array"].map(t => <option key={t} value={t}>{t}</option>)}
                      </select>
                      <label className="col-span-1 flex items-center justify-center gap-1 text-xs text-gray-500 cursor-pointer">
                        <input type="checkbox" checked={attr.required} onChange={e => updateAttr(i, "required", e.target.checked)} className="rounded" />
                        <span>{t("page.domains.required_checkbox_label")}</span>
                      </label>
                      <button
                        onClick={() => setFormAttrs(p => p.filter((_, idx) => idx !== i))}
                        disabled={formAttrs.length === 1}
                        aria-label={t("page.domains.delete_attribute_aria", { index: i + 1 })}
                        className="col-span-2 flex justify-center text-gray-400 hover:text-red-500 disabled:opacity-30 transition-colors"
                      >
                        <svg className="w-4 h-4" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Form footer */}
            <div className="flex justify-end gap-3 border-t border-gray-200 px-6 py-4 dark:border-gray-800">
              <button onClick={() => setShowForm(false)} className="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800">
                {t('page.domains.cancel_button')}
              </button>
              <button
                onClick={handleCreate}
                disabled={saving}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {saving ? t('page.domains.creating') : t('page.domains.create_button')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
