"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { PageHeader, TabNav, Badge, useToast } from "../../components/ui";
import MonteCarloChart from "../../components/MonteCarloChart";
import AnnotationThread from "../../components/AnnotationThread";
import EntityGraph from "../../components/EntityGraph";
import RelationshipManager from "../../components/RelationshipManager";
import PresenceAvatars from "../../components/PresenceAvatars";
import { useWebSocket } from "@/lib/useWebSocket";
import { useLanguage } from "../../contexts/LanguageContext";

type EntityValue =
    | string
    | number
    | boolean
    | null
    | undefined
    | string[]
    | number[]
    | Record<string, unknown>;

interface QualityBreakdownDimension {
    weight?: number;
    contribution?: number;
    raw?: number;
    score?: number;
    label?: string;
    explanation?: string;
}

interface EntityQualityData {
    score: number;
    stored_score: number | null;
    breakdown: Record<string, QualityBreakdownDimension>;
}

interface Entity {
    id: number;
    entity_name: string | null;
    brand_capitalized: string | null;
    brand_lower: string | null;
    model: string | null;
    sku: string | null;
    variant: string | null;
    classification: string | null;
    entity_type: string | null;
    status: string | null;
    validation_status: string;
    barcode: string | null;
    gtin: string | null;
    gtin_reason: string | null;
    unit_of_measure: string | null;
    measure: string | null;
    creation_date: string | null;
    enrichment_status: string;
    enrichment_doi: string | null;
    enrichment_citation_count: number;
    enrichment_concepts: string | null;
    enrichment_source: string | null;
    normalized_json: string | null;
    [key: string]: EntityValue;
}

interface AuthorityRecord {
    id: number;
    field_name: string;
    original_value: string;
    authority_source: string;
    authority_id: string;
    canonical_label: string;
    aliases: string[];
    description: string | null;
    confidence: number;
    uri: string | null;
    status: string;
    resolution_status: string;
}

type Tab = "overview" | "enrichment" | "authority" | "graph" | "comments";

const CORE_FIELDS: (keyof Entity)[] = [
    "entity_name", "brand_capitalized", "model", "sku", "variant",
    "classification", "entity_type", "status", "validation_status",
    "gtin", "barcode", "unit_of_measure", "measure", "creation_date",
];

const FIELD_TRANSLATION_KEYS: Record<string, string> = {
    entity_name: "entities.detail.field.entity_name",
    brand_capitalized: "entities.detail.field.brand_capitalized",
    model: "entities.detail.field.model",
    sku: "entities.detail.field.sku",
    variant: "entities.detail.field.variant",
    classification: "entities.detail.field.classification",
    entity_type: "entities.detail.field.entity_type",
    status: "entities.detail.field.status",
    validation_status: "entities.detail.field.validation_status",
    gtin: "entities.detail.field.gtin",
    barcode: "entities.detail.field.barcode",
    unit_of_measure: "entities.detail.field.unit_of_measure",
    measure: "entities.detail.field.measure",
    creation_date: "entities.detail.field.creation_date",
};

function sourceVariant(source: string) {
    return source === "wikidata" ? "warning" as const :
           source === "viaf" ? "info" as const :
           source === "orcid" ? "success" as const :
           source === "dbpedia" ? "error" as const :
           source === "openalex" ? "purple" as const : "default" as const;
}

function validationVariant(status: string) {
    return status === "valid" ? "success" as const :
           status === "invalid" ? "error" as const : "warning" as const;
}

function enrichmentVariant(status: string) {
    return status === "completed" ? "success" as const :
           status === "pending" ? "warning" as const :
           status === "failed" ? "error" as const : "default" as const;
}

const Spinner = () => (
    <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
);

export default function EntityDetailPage() {
    const params = useParams();
    const entityId = params.id as string;
    const { toast } = useToast();
    const { t } = useLanguage();

    // Real-time presence (Sprint 91)
    const { presence, isConnected, send: wsSend } = useWebSocket(
        entityId ? `entity-${entityId}` : null
    );

    const [entity, setEntity] = useState<Entity | null>(null);
    const [loading, setLoading] = useState(true);
    const [tab, setTab] = useState<Tab>("overview");

    // Edit mode
    const [isEditing, setIsEditing] = useState(false);
    const [editData, setEditData] = useState<Partial<Entity>>({});
    const [saving, setSaving] = useState(false);

    // Enrichment
    const [enriching, setEnriching] = useState(false);

    // Authority tab
    const [authorityRecords, setAuthorityRecords] = useState<AuthorityRecord[]>([]);
    const [authorityLoading, setAuthorityLoading] = useState(false);
    const [authorityAction, setAuthorityAction] = useState<number | null>(null);

    // Comments tab
    const [commentCount, setCommentCount] = useState<number>(0);

    // Graph tab
    const [graphKey, setGraphKey] = useState(0);

    // Quality score
    const [qualityData, setQualityData] = useState<EntityQualityData | null>(null);

    const fetchEntity = useCallback(async () => {
        setLoading(true);
        try {
            const res = await apiFetch(`/entities/${entityId}`);
            if (!res.ok) throw new Error("Not found");
            setEntity(await res.json());
        } catch {
            setEntity(null);
        } finally {
            setLoading(false);
        }
    }, [entityId]);

    useEffect(() => { fetchEntity(); }, [fetchEntity]);

    useEffect(() => {
        if (!entity) return;
        apiFetch(`/annotations?entity_id=${entity.id}&limit=200`)
            .then((r) => r.ok ? r.json() : [])
            .then((data: unknown[]) => setCommentCount(Array.isArray(data) ? data.length : 0))
            .catch(() => {});
    }, [entity]);

    const fetchAuthority = useCallback(async () => {
        if (!entity) return;
        setAuthorityLoading(true);
        try {
            const res = await apiFetch(`/authority/records?field_name=entity_name&limit=200`);
            if (res.ok) {
                const data = await res.json();
                const records: AuthorityRecord[] = data.records ?? data;
                const name = (entity.entity_name ?? "").toLowerCase();
                setAuthorityRecords(
                    records.filter((r: AuthorityRecord) =>
                        r.original_value.toLowerCase().includes(name) ||
                        name.includes(r.original_value.toLowerCase())
                    )
                );
            }
        } finally {
            setAuthorityLoading(false);
        }
    }, [entity]);

    useEffect(() => {
        if (tab === "authority" && entity) {
            fetchAuthority();
        }
    }, [tab, entity, fetchAuthority]);

    useEffect(() => {
        if (tab === "overview" && entity && !qualityData) {
            apiFetch(`/entities/${entity.id}/quality`)
                .then((r) => r.ok ? r.json() : null)
                .then((data: EntityQualityData | null) => { if (data) setQualityData(data); })
                .catch(() => {});
        }
    }, [tab, entity, qualityData]);

    function startEdit() {
        if (!entity) return;
        const data: Partial<Entity> = {};
        CORE_FIELDS.forEach((f) => { data[f] = entity[f]; });
        setEditData(data);
        setIsEditing(true);
        wsSend("entity.editing", { entity_id: Number(entityId), editing: true });
    }

    function cancelEdit() {
        setIsEditing(false);
        setEditData({});
        wsSend("entity.editing", { entity_id: Number(entityId), editing: false });
    }

    async function handleSave() {
        setSaving(true);
        try {
            const res = await apiFetch(`/entities/${entityId}`, {
                method: "PUT",
                body: JSON.stringify(editData),
            });
            if (!res.ok) throw new Error("Save failed");
            setEntity(await res.json());
            setIsEditing(false);
            setEditData({});
            toast("Entity saved", "success");
            wsSend("entity.saved", { entity_id: Number(entityId) });
        } catch {
            toast("Error saving entity", "error");
        } finally {
            setSaving(false);
        }
    }

    async function handleEnrich() {
        setEnriching(true);
        try {
            const res = await apiFetch(`/enrich/row/${entityId}`, { method: "POST" });
            if (res.ok) {
                setEntity(await res.json());
                setTab("enrichment");
            }
        } finally {
            setEnriching(false);
        }
    }

    async function confirmAuthority(recordId: number) {
        setAuthorityAction(recordId);
        try {
            await apiFetch(`/authority/records/${recordId}/confirm`, {
                method: "POST",
                body: JSON.stringify({ also_create_rule: true }),
            });
            setAuthorityRecords(prev =>
                prev.map(r => r.id === recordId ? { ...r, status: "confirmed" } : r)
            );
        } finally {
            setAuthorityAction(null);
        }
    }

    async function rejectAuthority(recordId: number) {
        setAuthorityAction(recordId);
        try {
            await apiFetch(`/authority/records/${recordId}/reject`, { method: "POST" });
            setAuthorityRecords(prev =>
                prev.map(r => r.id === recordId ? { ...r, status: "rejected" } : r)
            );
        } finally {
            setAuthorityAction(null);
        }
    }

    if (loading) {
        return (
            <div className="flex h-64 items-center justify-center">
                <svg className="h-8 w-8 animate-spin text-blue-600" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
            </div>
        );
    }

    if (!entity) {
        return (
            <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-gray-300 py-20 dark:border-gray-700">
                <p className="text-lg font-semibold text-gray-500 dark:text-gray-400">{t("entities.detail.not_found")}</p>
                <Link href="/" className="mt-3 text-sm text-blue-600 hover:underline dark:text-blue-400">
                    {t("entities.detail.back")}
                </Link>
            </div>
        );
    }

    const extendedAttrs: Record<string, unknown> = (() => {
        try { return entity.normalized_json ? JSON.parse(entity.normalized_json) : {}; }
        catch { return {}; }
    })();

    const description = [entity.brand_capitalized, entity.model].filter(Boolean).join(" · ");

    return (
        <div className="space-y-6">
            <PageHeader
                breadcrumbs={[
                    { label: t("entities.detail.breadcrumb.home"), href: "/" },
                    { label: t("entities.detail.breadcrumb.explorer"), href: "/" },
                    { label: entity.entity_name ?? `Entity #${entityId}` },
                ]}
                title={entity.entity_name ?? `Entity #${entityId}`}
                description={description || undefined}
                actions={
                    <div className="flex items-center gap-3">
                        <PresenceAvatars presence={presence} isConnected={isConnected} />
                        {isEditing ? (
                            <>
                                <button
                                    onClick={handleSave}
                                    disabled={saving}
                                    className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
                                >
                                    {saving ? <Spinner /> : null}
                                    {t("entities.detail.btn.save")}
                                </button>
                                <button
                                    onClick={cancelEdit}
                                    className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
                                >
                                    {t("entities.detail.btn.cancel")}
                                </button>
                            </>
                        ) : (
                            <button
                                onClick={startEdit}
                                className="flex items-center gap-2 rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
                            >
                                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                                </svg>
                                {t("entities.detail.btn.edit")}
                            </button>
                        )}
                        <button
                            onClick={handleEnrich}
                            disabled={enriching}
                            className="flex items-center gap-2 rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-purple-700 disabled:opacity-50"
                        >
                            {enriching ? <Spinner /> : (
                                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
                                </svg>
                            )}
                            {enriching ? t("entities.detail.btn.enriching") : t("entities.detail.btn.enrich")}
                        </button>
                    </div>
                }
            />

            <TabNav
                tabs={[
                    { id: "overview", label: t("entities.detail.tab.overview") },
                    { id: "enrichment", label: t("entities.detail.tab.enrichment") },
                    { id: "authority", label: t("entities.detail.tab.authority") },
                    { id: "graph", label: t("entities.detail.tab.graph") },
                    { id: "comments", label: t("entities.detail.tab.comments"), badge: commentCount > 0 ? commentCount : undefined },
                ]}
                activeTab={tab}
                onTabChange={(id) => setTab(id as Tab)}
            />

            {/* ── Overview ── */}
            {tab === "overview" && (
                <div className="space-y-6">
                    {/* Quality Score section */}
                    {qualityData && (
                        <div className="rounded-2xl border border-indigo-100 bg-white p-6 shadow-sm dark:border-indigo-500/20 dark:bg-gray-900">
                            <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-indigo-500 dark:text-indigo-400">
                                {t("entities.detail.section.quality")}
                            </h3>
                            <div className="flex items-center gap-6 mb-5">
                                <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-full border-4 border-indigo-100 dark:border-indigo-500/20 bg-indigo-50 dark:bg-indigo-500/10">
                                    <span className="text-2xl font-bold text-indigo-600 dark:text-indigo-400">
                                        {Math.round(qualityData.score * 100)}%
                                    </span>
                                </div>
                                <div>
                                    <p className="text-sm font-medium text-gray-700 dark:text-gray-300">{t("entities.detail.quality.overall")}</p>
                                    <div className="mt-1 w-48 h-2 rounded-full bg-gray-100 dark:bg-gray-800">
                                        <div
                                            className={`h-2 rounded-full ${qualityData.score >= 0.7 ? "bg-emerald-500" : qualityData.score >= 0.3 ? "bg-amber-400" : "bg-red-500"}`}
                                            style={{ width: `${Math.round(qualityData.score * 100)}%` }}
                                        />
                                    </div>
                                    {qualityData.stored_score != null && (
                                        <p className="mt-1 text-xs text-gray-400">{t("entities.detail.quality.stored")} {Math.round(qualityData.stored_score * 100)}%</p>
                                    )}
                                </div>
                            </div>
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-gray-100 dark:border-gray-800">
                                        <th className="pb-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-400">{t("entities.detail.quality.dimension")}</th>
                                        <th className="pb-2 text-right text-xs font-semibold uppercase tracking-wider text-gray-400">{t("entities.detail.quality.weight")}</th>
                                        <th className="pb-2 text-right text-xs font-semibold uppercase tracking-wider text-gray-400">{t("entities.detail.quality.contribution")}</th>
                                        <th className="pb-2 pl-4 text-left text-xs font-semibold uppercase tracking-wider text-gray-400">{t("entities.detail.quality.progress")}</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
                                    {Object.entries(qualityData.breakdown).map(([key, dim]) => {
                                        const weight = dim.weight ?? 0;
                                        const contribution = dim.contribution ?? 0;
                                        return (
                                        <tr key={key}>
                                            <td className="py-2 text-xs font-medium text-gray-600 dark:text-gray-300">
                                                {key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                                            </td>
                                            <td className="py-2 text-right text-xs text-gray-500">{Math.round(weight * 100)}%</td>
                                            <td className="py-2 text-right text-xs font-semibold text-indigo-600 dark:text-indigo-400">
                                                +{Math.round(contribution * 100)}%
                                            </td>
                                            <td className="py-2 pl-4">
                                                <div className="w-24 h-1.5 rounded-full bg-gray-100 dark:bg-gray-800">
                                                    <div
                                                        className="h-1.5 rounded-full bg-indigo-400"
                                                        style={{ width: weight > 0 ? `${(contribution / weight) * 100}%` : "0%" }}
                                                    />
                                                </div>
                                            </td>
                                        </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    )}
                    <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                        <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                            {t("entities.detail.section.core_fields")}
                        </h3>
                        <div className="grid grid-cols-1 gap-x-8 gap-y-5 md:grid-cols-2">
                            {CORE_FIELDS.map((field) => {
                                const label = t(FIELD_TRANSLATION_KEYS[field as string] ?? field as string);
                                const value = isEditing ? editData[field] : entity[field];
                                const isStatus = field === "validation_status";
                                const isEnrichStatus = field === "enrichment_status";

                                return (
                                    <div key={field as string} className="flex flex-col gap-1.5 border-b border-gray-50 pb-4 dark:border-gray-800/50">
                                        <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">
                                            {label}
                                        </span>
                                        {isEditing && !isStatus && !isEnrichStatus ? (
                                            <input
                                                value={(editData[field] as string) ?? ""}
                                                onChange={(e) => setEditData({ ...editData, [field]: e.target.value })}
                                                className="h-8 w-full rounded-lg border border-gray-200 bg-white px-2.5 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white"
                                            />
                                        ) : isStatus ? (
                                            <Badge variant={validationVariant(entity.validation_status)}>
                                                {entity.validation_status}
                                            </Badge>
                                        ) : isEnrichStatus ? (
                                            <Badge variant={enrichmentVariant(entity.enrichment_status)}>
                                                {entity.enrichment_status}
                                            </Badge>
                                        ) : (
                                            <span className="text-sm font-medium text-gray-800 dark:text-gray-200">
                                                {value ? String(value) : <span className="italic text-gray-300 dark:text-gray-600">—</span>}
                                            </span>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {Object.keys(extendedAttrs).length > 0 && (
                        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                            <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                                {t("entities.detail.section.extended_attrs")}
                            </h3>
                            <div className="grid grid-cols-1 gap-x-8 gap-y-5 md:grid-cols-2">
                                {Object.entries(extendedAttrs).map(([key, val]) => (
                                    <div key={key} className="flex flex-col gap-1.5 border-b border-gray-50 pb-4 dark:border-gray-800/50">
                                        <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">
                                            {key.replace(/_/g, " ")}
                                        </span>
                                        <span className="text-sm font-medium text-gray-800 dark:text-gray-200">
                                            {val !== null && val !== "" ? String(val) : <span className="italic text-gray-300 dark:text-gray-600">—</span>}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* ── Enrichment ── */}
            {tab === "enrichment" && (
                <div className="space-y-6">
                    <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                        {[
                            { label: t("entities.detail.enrichment.status"), value: <Badge variant={enrichmentVariant(entity.enrichment_status)}>{entity.enrichment_status}</Badge> },
                            { label: t("entities.detail.enrichment.citations"), value: entity.enrichment_citation_count || "—" },
                            { label: t("entities.detail.enrichment.source"), value: entity.enrichment_source || "—" },
                            { label: t("entities.detail.enrichment.doi"), value: entity.enrichment_doi ? (
                                <a href={`https://doi.org/${entity.enrichment_doi}`} target="_blank" rel="noopener noreferrer" className="truncate text-blue-600 hover:underline dark:text-blue-400">
                                    {entity.enrichment_doi}
                                </a>
                            ) : "—" },
                        ].map((s) => (
                            <div key={s.label} className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                                <p className="text-xs text-gray-500 dark:text-gray-400">{s.label}</p>
                                <div className="mt-1 text-sm font-semibold text-gray-900 dark:text-white">{s.value}</div>
                            </div>
                        ))}
                    </div>

                    {entity.enrichment_concepts && (
                        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                                {t("entities.detail.section.concepts")}
                            </p>
                            <div className="flex flex-wrap gap-2">
                                {entity.enrichment_concepts.split(",").map((c) => c.trim()).filter(Boolean).map((concept) => (
                                    <Badge key={concept} variant="info">{concept}</Badge>
                                ))}
                            </div>
                        </div>
                    )}

                    {entity.enrichment_status === "completed" ? (
                        <div className="rounded-2xl border border-purple-100 bg-white p-5 shadow-sm dark:border-purple-500/10 dark:bg-gray-900">
                            <MonteCarloChart productId={entity.id} />
                        </div>
                    ) : (
                        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-gray-300 py-16 dark:border-gray-700">
                            <svg className="mb-3 h-10 w-10 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
                            </svg>
                            <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
                                {entity.enrichment_status === "none"
                                    ? t("entities.detail.enrichment.not_started")
                                    : entity.enrichment_status === "failed"
                                    ? t("entities.detail.enrichment.failed")
                                    : t("entities.detail.enrichment.in_progress")}
                            </p>
                            {entity.enrichment_status !== "pending" && (
                                <button
                                    onClick={handleEnrich}
                                    disabled={enriching}
                                    className="mt-4 flex items-center gap-2 rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-purple-700 disabled:opacity-50"
                                >
                                    {enriching ? <Spinner /> : null}
                                    {enriching ? t("entities.detail.btn.enriching") : t("entities.detail.btn.enrich_now")}
                                </button>
                            )}
                        </div>
                    )}
                </div>
            )}

            {/* ── Graph ── */}
            {tab === "graph" && (
                <div className="space-y-6">
                    <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                        <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                            {t("entities.detail.section.relationship_graph")}
                        </h3>
                        <EntityGraph key={graphKey} entityId={entity.id} />
                    </div>
                    <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                        <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                            {t("entities.detail.section.manage_relationships")}
                        </h3>
                        <RelationshipManager
                            entityId={entity.id}
                            onRefreshGraph={() => setGraphKey((k) => k + 1)}
                        />
                    </div>
                </div>
            )}

            {/* ── Comments ── */}
            {tab === "comments" && (
                <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                    <AnnotationThread entityId={entity.id} />
                </div>
            )}

            {/* ── Authority ── */}
            {tab === "authority" && (
                <div>
                    {authorityLoading ? (
                        <div className="flex h-48 items-center justify-center">
                            <svg className="h-6 w-6 animate-spin text-blue-600" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                            </svg>
                        </div>
                    ) : authorityRecords.length === 0 ? (
                        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-gray-300 py-16 dark:border-gray-700">
                            <svg className="mb-3 h-10 w-10 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064" />
                            </svg>
                            <p className="text-sm font-medium text-gray-500 dark:text-gray-400">{t("entities.detail.authority.empty")}</p>
                            <Link href="/disambiguation" className="mt-3 text-sm text-blue-600 hover:underline dark:text-blue-400">
                                {t("entities.detail.authority.resolve_link")}
                            </Link>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {authorityRecords.map((rec) => {
                                const isActing = authorityAction === rec.id;
                                return (
                                    <div
                                        key={rec.id}
                                        className={`rounded-2xl border bg-white p-4 shadow-sm transition-opacity dark:bg-gray-900 ${
                                            rec.status === "rejected"
                                                ? "border-gray-200 opacity-50 dark:border-gray-800"
                                                : rec.status === "confirmed"
                                                ? "border-emerald-200 dark:border-emerald-700/50"
                                                : "border-gray-200 dark:border-gray-800"
                                        }`}
                                    >
                                        <div className="flex items-start justify-between gap-4">
                                            <div className="flex-1 min-w-0">
                                                <div className="flex flex-wrap items-center gap-2">
                                                    <Badge variant={sourceVariant(rec.authority_source)}>
                                                        {rec.authority_source.toUpperCase()}
                                                    </Badge>
                                                    <span className="text-sm font-semibold text-gray-900 dark:text-white">
                                                        {rec.canonical_label}
                                                    </span>
                                                    <Badge variant={
                                                        rec.status === "confirmed" ? "success" :
                                                        rec.status === "rejected" ? "default" : "warning"
                                                    }>{rec.status}</Badge>
                                                    {rec.uri && (
                                                        <a href={rec.uri} target="_blank" rel="noopener noreferrer"
                                                            className="text-gray-400 hover:text-blue-500 dark:text-gray-500">
                                                            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                                            </svg>
                                                        </a>
                                                    )}
                                                </div>
                                                {rec.description && (
                                                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400 line-clamp-2">
                                                        {rec.description}
                                                    </p>
                                                )}
                                                <div className="mt-2 flex items-center gap-2">
                                                    <div className="h-1.5 w-32 rounded-full bg-gray-200 dark:bg-gray-700">
                                                        <div className="h-1.5 rounded-full bg-blue-500"
                                                            style={{ width: `${Math.round(rec.confidence * 100)}%` }} />
                                                    </div>
                                                    <span className="text-xs text-gray-500">{t("entities.detail.authority.confidence", { pct: Math.round(rec.confidence * 100) })}</span>
                                                </div>
                                            </div>
                                            {rec.status === "pending" && (
                                                <div className="flex shrink-0 gap-2">
                                                    <button
                                                        onClick={() => confirmAuthority(rec.id)}
                                                        disabled={isActing}
                                                        className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-emerald-700 disabled:opacity-50"
                                                    >
                                                        {isActing ? "..." : t("entities.detail.authority.confirm")}
                                                    </button>
                                                    <button
                                                        onClick={() => rejectAuthority(rec.id)}
                                                        disabled={isActing}
                                                        className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-100 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
                                                    >
                                                        {isActing ? "..." : t("entities.detail.authority.reject")}
                                                    </button>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
