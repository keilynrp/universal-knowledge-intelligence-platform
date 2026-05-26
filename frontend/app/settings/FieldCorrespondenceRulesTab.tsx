"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { ToastVariant } from "../components/ui";

type Rule = {
  id: number;
  source_schema: string | null;
  source_field: string;
  canonical_target: string | null;
  semantic_concept: string | null;
  identifier_scheme: string | null;
  confidence: number;
  evidence: string[];
  is_active: boolean;
  created_from_suggestion_id: number | null;
};

type FormState = {
  id?: number;
  source_schema: string;
  source_field: string;
  canonical_target: string;
  semantic_concept: string;
  identifier_scheme: string;
  confidence: string;
  evidence: string;
};

type ImpactPreview = {
  affected_records: number;
  affected_import_batches: number;
  matching_suggestions: number;
  examples: Array<{
    entity_id: number;
    primary_label: string | null;
    import_batch_id: number | null;
    current_value: string | null;
    location: string;
  }>;
};

type GovernanceMetrics = {
  active_rules: number;
  inactive_rules: number;
  pending_suggestions: number;
  rejected_false_positives: number;
  ambiguous_sources: Array<{
    source_schema: string;
    pending_suggestions: number;
  }>;
};

type AuditEntry = {
  id: number;
  action: string;
  username: string | null;
  created_at: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
};

type ApplyResult = ImpactPreview & {
  dry_run: boolean;
  overwrite_existing: boolean;
  updated_records: number;
  skipped_existing: number;
  skipped_missing_value: number;
};

type PreventiveSeedResult = {
  created: number;
  updated: number;
  total_candidates: number;
};

type RuleJob = {
  id: number;
  rule_id: number | null;
  rule_label: string | null;
  username: string | null;
  records_updated: number;
  affected_records: number;
  skipped_existing: number;
  skipped_missing_value: number;
  fields_modified: string[];
  executed_at: string | null;
  reverted: boolean;
};

type EvidenceScore = {
  rule_id: number;
  score: "high" | "medium" | "low" | "none";
  affected_records: number;
  matching_suggestions: number;
  sample_values: string[];
};

const emptyForm: FormState = {
  source_schema: "",
  source_field: "",
  canonical_target: "canonical_id",
  semantic_concept: "persistent_identifier",
  identifier_scheme: "",
  confidence: "1",
  evidence: "manual_admin_rule",
};

function buildPayload(form: FormState) {
  return {
    source_schema: form.source_schema.trim() || null,
    source_field: form.source_field.trim(),
    canonical_target: form.canonical_target.trim() || null,
    semantic_concept: form.semantic_concept.trim() || null,
    identifier_scheme: form.identifier_scheme.trim() || null,
    confidence: Number(form.confidence || "1"),
    evidence: form.evidence
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
  };
}

function FormField({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  type?: string;
}) {
  return (
    <label className="block">
      <span className="text-xs font-semibold text-gray-600 dark:text-gray-300">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="mt-2 h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-900 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-800 dark:bg-gray-950 dark:text-white"
      />
    </label>
  );
}

export default function FieldCorrespondenceRulesTab({
  toast,
}: {
  toast: (msg: string, v?: ToastVariant) => void;
}) {
  const [rules, setRules] = useState<Rule[]>([]);
  const [sourceSchema, setSourceSchema] = useState("");
  const [activeOnly, setActiveOnly] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [impactPreview, setImpactPreview] = useState<ImpactPreview | null>(null);
  const [metrics, setMetrics] = useState<GovernanceMetrics | null>(null);
  const [auditByRule, setAuditByRule] = useState<Record<number, AuditEntry[]>>({});
  const [expandedAuditRuleId, setExpandedAuditRuleId] = useState<number | null>(null);
  const [applyResult, setApplyResult] = useState<ApplyResult | null>(null);
  const [jobs, setJobs] = useState<RuleJob[]>([]);
  const [evidenceScores, setEvidenceScores] = useState<Record<number, EvidenceScore>>({});
  const [applyingRuleId, setApplyingRuleId] = useState<number | null>(null);
  const [rollingBackJobId, setRollingBackJobId] = useState<number | null>(null);
  const [scoringEvidence, setScoringEvidence] = useState(false);
  const [seedingPreventiveRules, setSeedingPreventiveRules] = useState(false);
  const [form, setForm] = useState<FormState>(emptyForm);

  const fetchMetrics = useCallback(async () => {
    try {
      const response = await apiFetch("/field-correspondence-rules/governance-metrics");
      const data = await response.json().catch(() => null);
      if (response.ok) {
        setMetrics(data as GovernanceMetrics);
      }
    } catch {
      setMetrics(null);
    }
  }, []);

  const fetchJobs = useCallback(async () => {
    try {
      const response = await apiFetch("/field-correspondence-rules/jobs");
      const data = await response.json().catch(() => []);
      if (response.ok) {
        setJobs(data as RuleJob[]);
      }
    } catch {
      setJobs([]);
    }
  }, []);

  const fetchRules = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (sourceSchema.trim()) params.set("source_schema", sourceSchema.trim());
      if (activeOnly) params.set("active", "true");
      const suffix = params.toString() ? `?${params.toString()}` : "";
      const response = await apiFetch(`/field-correspondence-rules${suffix}`);
      const data = await response.json().catch(() => []);
      if (!response.ok) {
        throw new Error(data.detail ?? "No se pudieron cargar las reglas.");
      }
      setRules(data as Rule[]);
      await fetchMetrics();
      await fetchJobs();
    } catch (error) {
      toast(error instanceof Error ? error.message : "No se pudieron cargar las reglas.", "error");
    } finally {
      setLoading(false);
    }
  }, [activeOnly, fetchJobs, fetchMetrics, sourceSchema, toast]);

  useEffect(() => {
    void fetchRules();
  }, [fetchRules]);

  async function saveRule() {
    if (!form.source_field.trim()) {
      toast("El campo de origen es obligatorio.", "error");
      return;
    }
    setSaving(true);
    try {
      const response = await apiFetch(
        form.id ? `/field-correspondence-rules/${form.id}` : "/field-correspondence-rules",
        {
          method: form.id ? "PATCH" : "POST",
          body: JSON.stringify(buildPayload(form)),
        },
      );
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail ?? "No se pudo guardar la regla.");
      }
      toast(form.id ? "Regla actualizada." : "Regla creada.", "success");
      setForm(emptyForm);
      setImpactPreview(null);
      await fetchRules();
    } catch (error) {
      toast(error instanceof Error ? error.message : "No se pudo guardar la regla.", "error");
    } finally {
      setSaving(false);
    }
  }

  async function previewImpact() {
    if (!form.source_field.trim()) {
      toast("El campo de origen es obligatorio para previsualizar.", "error");
      return;
    }
    setPreviewing(true);
    try {
      const response = await apiFetch("/field-correspondence-rules/impact", {
        method: "POST",
        body: JSON.stringify(buildPayload(form)),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail ?? "No se pudo calcular el impacto.");
      }
      setImpactPreview(data as ImpactPreview);
    } catch (error) {
      toast(error instanceof Error ? error.message : "No se pudo calcular el impacto.", "error");
    } finally {
      setPreviewing(false);
    }
  }

  async function toggleRule(rule: Rule) {
    const action = rule.is_active ? "deactivate" : "reactivate";
    try {
      const response = await apiFetch(`/field-correspondence-rules/${rule.id}/${action}`, {
        method: "POST",
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail ?? "No se pudo cambiar el estado de la regla.");
      }
      toast(rule.is_active ? "Regla desactivada." : "Regla reactivada.", "success");
      await fetchRules();
    } catch (error) {
      toast(error instanceof Error ? error.message : "No se pudo cambiar el estado de la regla.", "error");
    }
  }

  function editRule(rule: Rule) {
    setForm({
      id: rule.id,
      source_schema: rule.source_schema ?? "",
      source_field: rule.source_field,
      canonical_target: rule.canonical_target ?? "",
      semantic_concept: rule.semantic_concept ?? "",
      identifier_scheme: rule.identifier_scheme ?? "",
      confidence: String(rule.confidence),
      evidence: rule.evidence.join(", "),
    });
    setImpactPreview(null);
  }

  async function fetchAudit(rule: Rule) {
    try {
      const response = await apiFetch(`/field-correspondence-rules/${rule.id}/audit`);
      const data = await response.json().catch(() => []);
      if (!response.ok) {
        throw new Error(data.detail ?? "No se pudo cargar la auditoria.");
      }
      setAuditByRule((current) => ({ ...current, [rule.id]: data as AuditEntry[] }));
    } catch (error) {
      toast(error instanceof Error ? error.message : "No se pudo cargar la auditoria.", "error");
    }
  }

  async function toggleAudit(rule: Rule) {
    if (expandedAuditRuleId === rule.id) {
      setExpandedAuditRuleId(null);
      return;
    }
    setExpandedAuditRuleId(rule.id);
    await fetchAudit(rule);
  }

  async function applyRule(rule: Rule, dryRun: boolean) {
    setApplyingRuleId(rule.id);
    try {
      const response = await apiFetch(`/field-correspondence-rules/${rule.id}/apply`, {
        method: "POST",
        body: JSON.stringify({ dry_run: dryRun, overwrite_existing: false }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail ?? "No se pudo procesar la regla.");
      }
      setApplyResult(data as ApplyResult);
      toast(dryRun ? "Preview de produccion calculado." : "Regla aplicada a registros existentes.", "success");
      await fetchRules();
      if (!dryRun) {
        setExpandedAuditRuleId(rule.id);
        await fetchAudit(rule);
        await fetchJobs();
      }
    } catch (error) {
      toast(error instanceof Error ? error.message : "No se pudo procesar la regla.", "error");
    } finally {
      setApplyingRuleId(null);
    }
  }

  async function seedPreventiveRules() {
    setSeedingPreventiveRules(true);
    try {
      const response = await apiFetch("/field-correspondence-rules/preventive-seed", {
        method: "POST",
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail ?? "No se pudieron cargar las reglas preventivas.");
      }
      const result = data as PreventiveSeedResult;
      toast(`Reglas preventivas cargadas: ${result.created} nuevas, ${result.updated} actualizadas.`, "success");
      setActiveOnly(false);
      await fetchRules();
    } catch (error) {
      toast(error instanceof Error ? error.message : "No se pudieron cargar las reglas preventivas.", "error");
    } finally {
      setSeedingPreventiveRules(false);
    }
  }

  async function rollbackJob(job: RuleJob) {
    setRollingBackJobId(job.id);
    try {
      const response = await apiFetch(`/field-correspondence-rules/jobs/${job.id}/rollback`, {
        method: "POST",
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail ?? "No se pudo revertir la ejecucion.");
      }
      toast(`Rollback completado: ${data.records_restored ?? 0} registros restaurados.`, "success");
      await fetchJobs();
      await fetchRules();
    } catch (error) {
      toast(error instanceof Error ? error.message : "No se pudo revertir la ejecucion.", "error");
    } finally {
      setRollingBackJobId(null);
    }
  }

  async function scoreEvidence() {
    setScoringEvidence(true);
    try {
      const params = new URLSearchParams();
      if (sourceSchema.trim()) params.set("source_schema", sourceSchema.trim());
      if (activeOnly) params.set("active", "true");
      params.set("limit", "300");
      const response = await apiFetch(`/field-correspondence-rules/evidence-scores?${params.toString()}`);
      const data = await response.json().catch(() => []);
      if (!response.ok) {
        throw new Error(data.detail ?? "No se pudo calcular la evidencia.");
      }
      const scores = data as EvidenceScore[];
      setEvidenceScores(Object.fromEntries(scores.map((item) => [item.rule_id, item])));
      toast("Evidencia calculada para las reglas visibles.", "success");
    } catch (error) {
      toast(error instanceof Error ? error.message : "No se pudo calcular la evidencia.", "error");
    } finally {
      setScoringEvidence(false);
    }
  }

  function evidenceBadge(score?: EvidenceScore) {
    if (!score) return <span className="text-xs text-gray-400">-</span>;
    const styles = {
      high: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300",
      medium: "bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300",
      low: "bg-sky-100 text-sky-700 dark:bg-sky-500/10 dark:text-sky-300",
      none: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300",
    }[score.score];
    const label = {
      high: "Alta",
      medium: "Media",
      low: "Baja",
      none: "Sin evidencia",
    }[score.score];
    return (
      <div className="flex flex-col gap-1">
        <span className={`w-fit rounded-full px-2 py-1 text-xs font-semibold ${styles}`}>{label}</span>
        <span className="text-[11px] text-gray-500 dark:text-gray-400">
          {score.affected_records} rec · {score.matching_suggestions} sug
        </span>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {metrics && (
        <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <div className="grid gap-4 md:grid-cols-4">
            <div>
              <p className="text-xs font-semibold text-gray-500 dark:text-gray-400">Reglas activas</p>
              <p className="mt-1 text-2xl font-semibold text-gray-900 dark:text-white">{metrics.active_rules}</p>
            </div>
            <div>
              <p className="text-xs font-semibold text-gray-500 dark:text-gray-400">Sugerencias pendientes</p>
              <p className="mt-1 text-2xl font-semibold text-amber-700 dark:text-amber-300">{metrics.pending_suggestions}</p>
            </div>
            <div>
              <p className="text-xs font-semibold text-gray-500 dark:text-gray-400">Falsos positivos rechazados</p>
              <p className="mt-1 text-2xl font-semibold text-red-700 dark:text-red-300">{metrics.rejected_false_positives}</p>
            </div>
            <div>
              <p className="text-xs font-semibold text-gray-500 dark:text-gray-400">Fuentes ambiguas</p>
              <p className="mt-1 text-sm font-semibold text-gray-900 dark:text-white">
                {metrics.ambiguous_sources.length
                  ? metrics.ambiguous_sources.map((source) => `${source.source_schema} (${source.pending_suggestions})`).join(", ")
                  : "-"}
              </p>
            </div>
          </div>
        </section>
      )}
      <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <div className="grid gap-4 lg:grid-cols-[1fr,auto,auto,auto]">
          <label className="block">
            <span className="text-xs font-semibold text-gray-600 dark:text-gray-300">Filtro por fuente</span>
            <input
              value={sourceSchema}
              onChange={(event) => setSourceSchema(event.target.value)}
              placeholder="wos, ris, bibtex, openalex..."
              className="mt-2 h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-900 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-800 dark:bg-gray-950 dark:text-white"
            />
          </label>
          <label className="flex items-end gap-2 pb-2 text-sm text-gray-700 dark:text-gray-300">
            <input
              type="checkbox"
              checked={activeOnly}
              onChange={(event) => setActiveOnly(event.target.checked)}
              className="h-4 w-4 rounded border-gray-300"
            />
            Solo activas
          </label>
          <button
            onClick={() => void fetchRules()}
            className="self-end rounded-lg border border-gray-200 px-4 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50 dark:border-gray-800 dark:text-gray-300 dark:hover:bg-gray-800"
          >
            Actualizar
          </button>
          <button
            onClick={() => void seedPreventiveRules()}
            disabled={seedingPreventiveRules}
            className="self-end rounded-lg border border-amber-200 px-4 py-2 text-sm font-semibold text-amber-700 hover:bg-amber-50 disabled:opacity-50 dark:border-amber-900/40 dark:text-amber-300 dark:hover:bg-amber-950/30"
          >
            {seedingPreventiveRules ? "Cargando..." : "Cargar preventivas"}
          </button>
        </div>
      </section>

      <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <h3 className="text-base font-semibold text-gray-900 dark:text-white">
          {form.id ? "Editar regla" : "Nueva regla"}
        </h3>
        <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <FormField
            label="Fuente"
            value={form.source_schema}
            onChange={(value) => setForm({ ...form, source_schema: value })}
            placeholder="wos"
          />
          <FormField
            label="Campo origen"
            value={form.source_field}
            onChange={(value) => setForm({ ...form, source_field: value })}
            placeholder="DI"
          />
          <FormField
            label="Destino canonico"
            value={form.canonical_target}
            onChange={(value) => setForm({ ...form, canonical_target: value })}
            placeholder="canonical_id"
          />
          <FormField
            label="Concepto semantico"
            value={form.semantic_concept}
            onChange={(value) => setForm({ ...form, semantic_concept: value })}
            placeholder="persistent_identifier"
          />
          <FormField
            label="Esquema"
            value={form.identifier_scheme}
            onChange={(value) => setForm({ ...form, identifier_scheme: value })}
            placeholder="doi, orcid, ror, local"
          />
          <FormField
            label="Confianza"
            type="number"
            value={form.confidence}
            onChange={(value) => setForm({ ...form, confidence: value })}
            placeholder="1"
          />
          <div className="md:col-span-2 xl:col-span-3">
            <FormField
              label="Evidencia"
              value={form.evidence}
              onChange={(value) => setForm({ ...form, evidence: value })}
              placeholder="manual_admin_rule"
            />
          </div>
        </div>
        <div className="mt-5 flex flex-col gap-3 sm:flex-row">
          <button
            onClick={() => void saveRule()}
            disabled={saving}
            className="rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {saving ? "Guardando..." : form.id ? "Actualizar regla" : "Crear regla"}
          </button>
          <button
            onClick={() => void previewImpact()}
            disabled={previewing}
            className="rounded-lg border border-blue-200 px-4 py-2.5 text-sm font-semibold text-blue-700 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-blue-900/40 dark:text-blue-300 dark:hover:bg-blue-950/30"
          >
            {previewing ? "Calculando..." : "Previsualizar impacto"}
          </button>
          {form.id && (
            <button
              onClick={() => {
                setForm(emptyForm);
                setImpactPreview(null);
              }}
              className="rounded-lg border border-gray-200 px-4 py-2.5 text-sm font-semibold text-gray-700 hover:bg-gray-50 dark:border-gray-800 dark:text-gray-300 dark:hover:bg-gray-800"
            >
              Cancelar edicion
            </button>
          )}
        </div>
        {impactPreview && (
          <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50/70 p-4 dark:border-amber-900/40 dark:bg-amber-950/20">
            <div className="grid gap-3 sm:grid-cols-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-amber-700 dark:text-amber-300">Registros</p>
                <p className="mt-1 text-lg font-semibold text-amber-950 dark:text-amber-100">{impactPreview.affected_records}</p>
              </div>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-amber-700 dark:text-amber-300">Batches</p>
                <p className="mt-1 text-lg font-semibold text-amber-950 dark:text-amber-100">{impactPreview.affected_import_batches}</p>
              </div>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-amber-700 dark:text-amber-300">Sugerencias</p>
                <p className="mt-1 text-lg font-semibold text-amber-950 dark:text-amber-100">{impactPreview.matching_suggestions}</p>
              </div>
            </div>
            {impactPreview.examples.length > 0 && (
              <div className="mt-4 space-y-2">
                {impactPreview.examples.map((example) => (
                  <div key={example.entity_id} className="rounded-lg bg-white/70 px-3 py-2 text-xs text-amber-950 dark:bg-gray-950/50 dark:text-amber-100">
                    <span className="font-semibold">#{example.entity_id}</span>
                    {example.primary_label ? ` · ${example.primary_label}` : ""}
                    {example.current_value ? ` · ${example.current_value}` : ""}
                    <span className="text-amber-700 dark:text-amber-300"> · {example.location}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        {applyResult && (
          <div className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50/70 p-4 dark:border-emerald-900/40 dark:bg-emerald-950/20">
            <div className="grid gap-3 sm:grid-cols-4">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-emerald-700 dark:text-emerald-300">Modo</p>
                <p className="mt-1 text-sm font-semibold text-emerald-950 dark:text-emerald-100">{applyResult.dry_run ? "Preview" : "Aplicado"}</p>
              </div>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-emerald-700 dark:text-emerald-300">Actualizables</p>
                <p className="mt-1 text-lg font-semibold text-emerald-950 dark:text-emerald-100">{applyResult.updated_records}</p>
              </div>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-emerald-700 dark:text-emerald-300">Ya tenian valor</p>
                <p className="mt-1 text-lg font-semibold text-emerald-950 dark:text-emerald-100">{applyResult.skipped_existing}</p>
              </div>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-emerald-700 dark:text-emerald-300">Sin valor origen</p>
                <p className="mt-1 text-lg font-semibold text-emerald-950 dark:text-emerald-100">{applyResult.skipped_missing_value}</p>
              </div>
            </div>
          </div>
        )}
      </section>

      <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-base font-semibold text-gray-900 dark:text-white">Ejecuciones de produccion</h3>
          <button onClick={() => void fetchJobs()} className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-semibold text-gray-700 hover:bg-gray-50 dark:border-gray-800 dark:text-gray-300 dark:hover:bg-gray-800">
            Actualizar jobs
          </button>
        </div>
        {jobs.length === 0 ? (
          <p className="mt-5 text-sm text-gray-500 dark:text-gray-400">No hay ejecuciones productivas registradas.</p>
        ) : (
          <div className="mt-5 overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-gray-200 text-xs uppercase tracking-[0.14em] text-gray-500 dark:border-gray-800 dark:text-gray-400">
                <tr>
                  <th className="py-3 pr-4">Fecha</th>
                  <th className="py-3 pr-4">Regla</th>
                  <th className="py-3 pr-4">Usuario</th>
                  <th className="py-3 pr-4">Actualizados</th>
                  <th className="py-3 pr-4">Omitidos</th>
                  <th className="py-3 pr-4">Estado</th>
                  <th className="py-3 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                {jobs.map((job) => (
                  <tr key={job.id}>
                    <td className="py-3 pr-4 text-xs text-gray-600 dark:text-gray-300">{job.executed_at ? new Date(job.executed_at).toLocaleString() : "-"}</td>
                    <td className="py-3 pr-4 font-mono text-xs text-gray-900 dark:text-white">{job.rule_label ?? `#${job.rule_id ?? job.id}`}</td>
                    <td className="py-3 pr-4 text-xs text-gray-600 dark:text-gray-300">{job.username ?? "-"}</td>
                    <td className="py-3 pr-4 text-xs font-semibold text-emerald-700 dark:text-emerald-300">{job.records_updated}</td>
                    <td className="py-3 pr-4 text-xs text-gray-500 dark:text-gray-400">{job.skipped_existing + job.skipped_missing_value}</td>
                    <td className="py-3 pr-4">
                      <span className={`rounded-full px-2 py-1 text-xs font-semibold ${job.reverted ? "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300" : "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300"}`}>
                        {job.reverted ? "Revertida" : "Aplicada"}
                      </span>
                    </td>
                    <td className="py-3 text-right">
                      <button
                        onClick={() => void rollbackJob(job)}
                        disabled={job.reverted || rollingBackJobId === job.id}
                        className="rounded-lg border border-red-200 px-3 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-50 disabled:opacity-50 dark:border-red-900/40 dark:text-red-300 dark:hover:bg-red-950/30"
                      >
                        {rollingBackJobId === job.id ? "Revirtiendo..." : "Rollback"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-base font-semibold text-gray-900 dark:text-white">Reglas existentes</h3>
          <div className="flex items-center gap-2">
            <button
              onClick={() => void scoreEvidence()}
              disabled={scoringEvidence}
              className="rounded-lg border border-sky-200 px-3 py-1.5 text-xs font-semibold text-sky-700 hover:bg-sky-50 disabled:opacity-50 dark:border-sky-900/40 dark:text-sky-300 dark:hover:bg-sky-950/30"
            >
              {scoringEvidence ? "Calculando..." : "Calcular evidencia"}
            </button>
            <span className="text-xs font-semibold text-gray-500 dark:text-gray-400">{rules.length} reglas</span>
          </div>
        </div>
        {loading ? (
          <p className="mt-5 text-sm text-gray-500 dark:text-gray-400">Cargando reglas...</p>
        ) : rules.length === 0 ? (
          <p className="mt-5 text-sm text-gray-500 dark:text-gray-400">No hay reglas con estos filtros.</p>
        ) : (
          <div className="mt-5 overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-gray-200 text-xs uppercase tracking-[0.14em] text-gray-500 dark:border-gray-800 dark:text-gray-400">
                <tr>
                  <th className="py-3 pr-4">Fuente</th>
                  <th className="py-3 pr-4">Campo</th>
                  <th className="py-3 pr-4">Destino</th>
                  <th className="py-3 pr-4">Concepto</th>
                  <th className="py-3 pr-4">Evidencia</th>
                  <th className="py-3 pr-4">Score</th>
                  <th className="py-3 pr-4">Estado</th>
                  <th className="py-3 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                {rules.map((rule) => (
                  <Fragment key={rule.id}>
                    <tr>
                      <td className="py-3 pr-4 font-mono text-xs text-gray-700 dark:text-gray-300">{rule.source_schema ?? "*"}</td>
                      <td className="py-3 pr-4 font-mono text-xs text-gray-900 dark:text-white">{rule.source_field}</td>
                      <td className="py-3 pr-4 font-mono text-xs text-emerald-700 dark:text-emerald-300">{rule.canonical_target ?? "ignore"}</td>
                      <td className="py-3 pr-4 text-xs text-gray-600 dark:text-gray-300">
                        {rule.semantic_concept ?? "-"}
                        {rule.identifier_scheme ? ` / ${rule.identifier_scheme}` : ""}
                      </td>
                      <td className="py-3 pr-4 text-xs text-gray-500 dark:text-gray-400">{rule.evidence.join(", ") || "-"}</td>
                      <td className="py-3 pr-4">{evidenceBadge(evidenceScores[rule.id])}</td>
                      <td className="py-3 pr-4">
                        <span className={`rounded-full px-2 py-1 text-xs font-semibold ${rule.is_active ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300" : "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300"}`}>
                          {rule.is_active ? "Activa" : "Inactiva"}
                        </span>
                      </td>
                      <td className="py-3 text-right">
                        <div className="flex flex-wrap justify-end gap-2">
                          <button onClick={() => editRule(rule)} className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-semibold text-gray-700 hover:bg-gray-50 dark:border-gray-800 dark:text-gray-300 dark:hover:bg-gray-800">
                            Editar
                          </button>
                          <button onClick={() => void toggleAudit(rule)} className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-semibold text-gray-700 hover:bg-gray-50 dark:border-gray-800 dark:text-gray-300 dark:hover:bg-gray-800">
                            Historial
                          </button>
                          <button onClick={() => void applyRule(rule, true)} disabled={applyingRuleId === rule.id || !rule.is_active} className="rounded-lg border border-emerald-200 px-3 py-1.5 text-xs font-semibold text-emerald-700 hover:bg-emerald-50 disabled:opacity-50 dark:border-emerald-900/40 dark:text-emerald-300 dark:hover:bg-emerald-950/30">
                            Preview prod
                          </button>
                          <button onClick={() => void applyRule(rule, false)} disabled={applyingRuleId === rule.id || !rule.is_active} className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700 disabled:opacity-50">
                            Aplicar
                          </button>
                          <button onClick={() => void toggleRule(rule)} className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-semibold text-gray-700 hover:bg-gray-50 dark:border-gray-800 dark:text-gray-300 dark:hover:bg-gray-800">
                            {rule.is_active ? "Desactivar" : "Reactivar"}
                          </button>
                        </div>
                      </td>
                    </tr>
                    {expandedAuditRuleId === rule.id && (
                      <tr>
                        <td colSpan={8} className="bg-gray-50 px-4 py-3 dark:bg-gray-950/40">
                          <div className="space-y-2">
                            {(auditByRule[rule.id] ?? []).length === 0 ? (
                              <p className="text-xs text-gray-500 dark:text-gray-400">Sin cambios registrados.</p>
                            ) : (
                              (auditByRule[rule.id] ?? []).map((entry) => (
                                <div key={entry.id} className="rounded-lg bg-white px-3 py-2 text-xs text-gray-700 dark:bg-gray-900 dark:text-gray-300">
                                  <div className="flex flex-wrap items-center justify-between gap-2">
                                    <span className="font-semibold">{entry.action}</span>
                                    <span className="text-gray-500 dark:text-gray-400">{entry.username ?? "-"} · {entry.created_at ? new Date(entry.created_at).toLocaleString() : "-"}</span>
                                  </div>
                                  <div className="mt-1 font-mono text-[11px] text-gray-500 dark:text-gray-400">
                                    {entry.before?.identifier_scheme !== entry.after?.identifier_scheme && (
                                      <span>scheme: {String(entry.before?.identifier_scheme ?? "-")} → {String(entry.after?.identifier_scheme ?? "-")} </span>
                                    )}
                                    {entry.before?.canonical_target !== entry.after?.canonical_target && (
                                      <span>target: {String(entry.before?.canonical_target ?? "-")} → {String(entry.after?.canonical_target ?? "-")} </span>
                                    )}
                                    {entry.before?.is_active !== entry.after?.is_active && (
                                      <span>active: {String(entry.before?.is_active ?? "-")} → {String(entry.after?.is_active ?? "-")}</span>
                                    )}
                                  </div>
                                </div>
                              ))
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
