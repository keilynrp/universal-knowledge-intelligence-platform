"use client";

import { useState, type ReactNode } from "react";
import { apiFetch } from "@/lib/api";
import type { ToastVariant } from "../components/ui";
import { EntityConcept } from "../components/ui";

type CanonicalIdentityResult = {
  mode: "dry-run" | "applied";
  scanned: number;
  fixed_canonical_id: number;
  fixed_entity_type: number;
  skipped_duplicates: number;
};

type OnlyField = "" | "canonical_id" | "entity_type";

function ResultMetric({ label, value }: { label: ReactNode; value: number | string }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-800 dark:bg-gray-950/40">
      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-500 dark:text-gray-400">
        {label}
      </p>
      <p className="mt-2 text-sm font-semibold text-gray-900 dark:text-white">{value}</p>
    </div>
  );
}

export default function DataFixesTab({
  toast,
}: {
  toast: (msg: string, v?: ToastVariant) => void;
}) {
  const [only, setOnly] = useState<OnlyField>("");
  const [orgId, setOrgId] = useState("");
  const [limit, setLimit] = useState("");
  const [runningMode, setRunningMode] = useState<"dry-run" | "apply" | null>(null);
  const [lastResult, setLastResult] = useState<CanonicalIdentityResult | null>(null);

  const hasPreview = lastResult?.mode === "dry-run";
  const canApply = Boolean(hasPreview) && !runningMode;

  function buildPayload(dryRun: boolean) {
    return {
      dry_run: dryRun,
      ...(only ? { only } : {}),
      ...(orgId.trim() ? { org_id: Number(orgId) } : {}),
      ...(limit.trim() ? { limit: Number(limit) } : {}),
    };
  }

  async function runCanonicalIdentityFix(dryRun: boolean) {
    setRunningMode(dryRun ? "dry-run" : "apply");
    try {
      const response = await apiFetch("/admin/data-fixes/canonical-identity", {
        method: "POST",
        body: JSON.stringify(buildPayload(dryRun)),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail ?? "No se pudo ejecutar el backfill canonico.");
      }
      const result = data as CanonicalIdentityResult;
      setLastResult(result);
      toast(
        dryRun
          ? "Simulacion completada. Revisa los contadores antes de aplicar."
          : "Backfill canonico aplicado correctamente.",
        "success",
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : "No se pudo ejecutar el backfill canonico.";
      toast(message, "error");
    } finally {
      setRunningMode(null);
    }
  }

  return (
    <div className="space-y-5">
      <div className="rounded-2xl border border-blue-200 bg-blue-50/80 p-4 shadow-sm dark:border-blue-900/30 dark:bg-blue-900/10">
        <p className="text-sm font-semibold text-blue-950 dark:text-blue-100">
          Reparacion de identidad canonica para registros existentes
        </p>
        <p className="mt-1 text-xs leading-5 text-blue-900/80 dark:text-blue-200/80">
          Usa este flujo cuando registros ya importados tienen DOI, ORCID, ROR o tipo de entidad guardados en campos de
          enriquecimiento/atributos, pero la ficha muestra ID canonico o tipo vacios. Primero ejecuta una simulacion.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[0.95fr,1.05fr]">
        <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <h3 className="text-base font-semibold text-gray-900 dark:text-white">Parametros</h3>
          <div className="mt-5 space-y-4">
            <label className="block">
              <span className="text-xs font-semibold text-gray-600 dark:text-gray-300">Campo a reparar</span>
              <select
                value={only}
                onChange={(event) => setOnly(event.target.value as OnlyField)}
                className="mt-2 h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-900 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-800 dark:bg-gray-950 dark:text-white"
              >
                <option value="">Ambos campos</option>
                <option value="canonical_id">Solo ID canonico</option>
                <option value="entity_type">Solo tipo de entidad</option>
              </select>
            </label>

            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block">
                <span className="text-xs font-semibold text-gray-600 dark:text-gray-300">Org ID</span>
                <input
                  type="number"
                  min={1}
                  value={orgId}
                  onChange={(event) => setOrgId(event.target.value)}
                  placeholder="Todas"
                  className="mt-2 h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-900 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-800 dark:bg-gray-950 dark:text-white"
                />
              </label>
              <label className="block">
                <span className="text-xs font-semibold text-gray-600 dark:text-gray-300">Limite</span>
                <input
                  type="number"
                  min={1}
                  value={limit}
                  onChange={(event) => setLimit(event.target.value)}
                  placeholder="Sin limite"
                  className="mt-2 h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-900 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-800 dark:bg-gray-950 dark:text-white"
                />
              </label>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row">
              <button
                onClick={() => void runCanonicalIdentityFix(true)}
                disabled={Boolean(runningMode)}
                className="inline-flex flex-1 items-center justify-center rounded-xl border border-blue-200 bg-white px-4 py-2.5 text-sm font-semibold text-blue-700 transition hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-blue-900/40 dark:bg-gray-950 dark:text-blue-300 dark:hover:bg-blue-950/30"
              >
                {runningMode === "dry-run" ? "Simulando..." : "Simular"}
              </button>
              <button
                onClick={() => void runCanonicalIdentityFix(false)}
                disabled={!canApply}
                className="inline-flex flex-1 items-center justify-center rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {runningMode === "apply" ? "Aplicando..." : "Aplicar resultado"}
              </button>
            </div>

            {!hasPreview && (
              <p className="text-xs leading-5 text-gray-500 dark:text-gray-400">
                El boton de aplicar se habilita despues de una simulacion para evitar cambios accidentales.
              </p>
            )}
          </div>
        </section>

        <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="text-base font-semibold text-gray-900 dark:text-white">Ultimo resultado</h3>
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                El backfill no sobreescribe valores existentes y omite duplicados que romperian unicidad.
              </p>
            </div>
            {lastResult && (
              <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-semibold text-gray-700 dark:bg-gray-800 dark:text-gray-300">
                {lastResult.mode === "dry-run" ? "Simulacion" : "Aplicado"}
              </span>
            )}
          </div>

          {lastResult ? (
            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              <ResultMetric label="Escaneados" value={lastResult.scanned} />
              <ResultMetric label="ID canonico" value={lastResult.fixed_canonical_id} />
              <ResultMetric label={<EntityConcept>Tipo entidad</EntityConcept>} value={lastResult.fixed_entity_type} />
              <ResultMetric label="Duplicados omitidos" value={lastResult.skipped_duplicates} />
            </div>
          ) : (
            <div className="mt-5 rounded-xl border border-dashed border-gray-200 px-4 py-10 text-center dark:border-gray-800">
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Aun no hay resultados.</p>
              <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                Ejecuta una simulacion para estimar cuantos registros se repararian.
              </p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
