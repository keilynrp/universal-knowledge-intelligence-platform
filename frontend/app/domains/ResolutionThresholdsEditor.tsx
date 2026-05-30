"use client";

import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api";

interface ResolutionThreshold {
  id: number;
  org_id: number | null;
  domain_id: string | null;
  field_name: string;
  exact: number;
  probable: number;
  ambiguous: number;
}

interface ResolutionThresholdsEditorProps {
  domainId: string;
}

const DEFAULTS = { exact: 0.85, probable: 0.65, ambiguous: 0.45 };

/**
 * Per-domain editor for adaptive authority resolution thresholds (Task 11).
 * Lists existing overrides for the selected domain and lets an admin create,
 * update, or delete the exact/probable/ambiguous cut points used to classify
 * a candidate score into a resolution_status.
 */
export default function ResolutionThresholdsEditor({ domainId }: ResolutionThresholdsEditorProps) {
  const [rows, setRows] = useState<ResolutionThreshold[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [fieldName, setFieldName] = useState("");
  const [exact, setExact] = useState(DEFAULTS.exact);
  const [probable, setProbable] = useState(DEFAULTS.probable);
  const [ambiguous, setAmbiguous] = useState(DEFAULTS.ambiguous);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch("/authority/thresholds");
      if (!res.ok) throw new Error(`Failed to load thresholds (${res.status})`);
      const data: ResolutionThreshold[] = await res.json();
      setRows(data.filter((r) => r.domain_id === domainId));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load thresholds");
    } finally {
      setLoading(false);
    }
  }, [domainId]);

  useEffect(() => {
    void load();
  }, [load]);

  const ordered = exact > probable && probable > ambiguous;

  const save = async () => {
    if (!fieldName.trim()) {
      setError("Field name is required");
      return;
    }
    if (!ordered) {
      setError("Thresholds must satisfy exact > probable > ambiguous");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const res = await apiFetch("/authority/thresholds", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          field_name: fieldName.trim(),
          domain_id: domainId,
          exact,
          probable,
          ambiguous,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: "Save failed" }));
        throw new Error(typeof body.detail === "string" ? body.detail : "Save failed");
      }
      setFieldName("");
      setExact(DEFAULTS.exact);
      setProbable(DEFAULTS.probable);
      setAmbiguous(DEFAULTS.ambiguous);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id: number) => {
    setError(null);
    try {
      const res = await apiFetch(`/authority/thresholds/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error(`Delete failed (${res.status})`);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
  };

  return (
    <div className="overflow-y-auto flex-1 p-4 space-y-5">
      <div>
        <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-200">
          Umbrales de resolución
        </h3>
        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
          Ajusta los cortes que clasifican una puntuación en{" "}
          <span className="font-medium">exacto / probable / ambiguo</span>. Si no defines un
          override, se usan los valores por defecto ({DEFAULTS.exact} / {DEFAULTS.probable} /{" "}
          {DEFAULTS.ambiguous}).
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-300">
          {error}
        </div>
      )}

      {/* Existing overrides */}
      <div className="space-y-2">
        {loading ? (
          <p className="text-xs text-gray-400">Cargando…</p>
        ) : rows.length === 0 ? (
          <p className="text-xs text-gray-400">Sin overrides para este dominio.</p>
        ) : (
          rows.map((r) => (
            <div
              key={r.id}
              className="flex items-center justify-between rounded-lg border border-gray-200 px-3 py-2 dark:border-gray-800"
            >
              <div className="text-xs">
                <span className="font-medium text-gray-800 dark:text-gray-200">{r.field_name}</span>
                <span className="ml-2 text-gray-500 dark:text-gray-400">
                  {r.exact} / {r.probable} / {r.ambiguous}
                </span>
              </div>
              <button
                onClick={() => remove(r.id)}
                className="rounded-md px-2 py-1 text-xs text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-900/20"
              >
                Eliminar
              </button>
            </div>
          ))
        )}
      </div>

      {/* New / update override form */}
      <div className="rounded-xl border border-gray-200 p-3 dark:border-gray-800 space-y-3">
        <div>
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400">Campo</label>
          <input
            value={fieldName}
            onChange={(e) => setFieldName(e.target.value)}
            placeholder="author"
            className="mt-1 w-full rounded-lg border border-gray-300 px-2.5 py-1.5 text-sm dark:border-gray-700 dark:bg-gray-900"
          />
        </div>
        <div className="grid grid-cols-3 gap-2">
          {([
            ["Exacto", exact, setExact],
            ["Probable", probable, setProbable],
            ["Ambiguo", ambiguous, setAmbiguous],
          ] as const).map(([label, value, setter]) => (
            <div key={label}>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400">{label}</label>
              <input
                type="number"
                step="0.01"
                min={0}
                max={1}
                value={value}
                onChange={(e) => setter(parseFloat(e.target.value))}
                className="mt-1 w-full rounded-lg border border-gray-300 px-2.5 py-1.5 text-sm dark:border-gray-700 dark:bg-gray-900"
              />
            </div>
          ))}
        </div>
        {!ordered && (
          <p className="text-xs text-amber-600 dark:text-amber-400">
            Debe cumplirse exacto &gt; probable &gt; ambiguo.
          </p>
        )}
        <button
          onClick={save}
          disabled={saving || !ordered}
          className="rounded-lg bg-violet-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50"
        >
          {saving ? "Guardando…" : "Guardar override"}
        </button>
      </div>
    </div>
  );
}
