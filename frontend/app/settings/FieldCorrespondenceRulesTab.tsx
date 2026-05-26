"use client";

import { useCallback, useEffect, useState } from "react";
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
  const [form, setForm] = useState<FormState>(emptyForm);

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
    } catch (error) {
      toast(error instanceof Error ? error.message : "No se pudieron cargar las reglas.", "error");
    } finally {
      setLoading(false);
    }
  }, [activeOnly, sourceSchema, toast]);

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
      await fetchRules();
    } catch (error) {
      toast(error instanceof Error ? error.message : "No se pudo guardar la regla.", "error");
    } finally {
      setSaving(false);
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
  }

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <div className="grid gap-4 lg:grid-cols-[1fr,auto,auto]">
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
          {form.id && (
            <button
              onClick={() => setForm(emptyForm)}
              className="rounded-lg border border-gray-200 px-4 py-2.5 text-sm font-semibold text-gray-700 hover:bg-gray-50 dark:border-gray-800 dark:text-gray-300 dark:hover:bg-gray-800"
            >
              Cancelar edicion
            </button>
          )}
        </div>
      </section>

      <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-base font-semibold text-gray-900 dark:text-white">Reglas existentes</h3>
          <span className="text-xs font-semibold text-gray-500 dark:text-gray-400">{rules.length} reglas</span>
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
                  <th className="py-3 pr-4">Estado</th>
                  <th className="py-3 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                {rules.map((rule) => (
                  <tr key={rule.id}>
                    <td className="py-3 pr-4 font-mono text-xs text-gray-700 dark:text-gray-300">{rule.source_schema ?? "*"}</td>
                    <td className="py-3 pr-4 font-mono text-xs text-gray-900 dark:text-white">{rule.source_field}</td>
                    <td className="py-3 pr-4 font-mono text-xs text-emerald-700 dark:text-emerald-300">{rule.canonical_target ?? "ignore"}</td>
                    <td className="py-3 pr-4 text-xs text-gray-600 dark:text-gray-300">
                      {rule.semantic_concept ?? "-"}
                      {rule.identifier_scheme ? ` / ${rule.identifier_scheme}` : ""}
                    </td>
                    <td className="py-3 pr-4 text-xs text-gray-500 dark:text-gray-400">{rule.evidence.join(", ") || "-"}</td>
                    <td className="py-3 pr-4">
                      <span className={`rounded-full px-2 py-1 text-xs font-semibold ${rule.is_active ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300" : "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300"}`}>
                        {rule.is_active ? "Activa" : "Inactiva"}
                      </span>
                    </td>
                    <td className="py-3 text-right">
                      <div className="flex justify-end gap-2">
                        <button onClick={() => editRule(rule)} className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-semibold text-gray-700 hover:bg-gray-50 dark:border-gray-800 dark:text-gray-300 dark:hover:bg-gray-800">
                          Editar
                        </button>
                        <button onClick={() => void toggleRule(rule)} className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-semibold text-gray-700 hover:bg-gray-50 dark:border-gray-800 dark:text-gray-300 dark:hover:bg-gray-800">
                          {rule.is_active ? "Desactivar" : "Reactivar"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
