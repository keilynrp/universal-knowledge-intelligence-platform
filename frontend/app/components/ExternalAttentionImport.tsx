"use client";

import { useState, useRef } from "react";
import { apiFetch } from "@/lib/api";
import { useLanguage } from "../contexts/LanguageContext";

interface ImportResult {
  imported: number;
  skipped: number;
  entities_updated: number;
  warnings: string[];
}

export default function ExternalAttentionImport() {
  const { t } = useLanguage();
  const [mode, setMode] = useState<"json" | "csv">("csv");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [jsonInput, setJsonInput] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleCSVUpload() {
    const file = fileRef.current?.files?.[0];
    if (!file) return;

    setLoading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const resp = await apiFetch("/external-attention/import/csv", {
        method: "POST",
        body: formData,
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => null);
        throw new Error(body?.detail || `HTTP ${resp.status}`);
      }
      setResult(await resp.json());
    } catch (e: any) {
      setError(e.message || "Import failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleJSONImport() {
    if (!jsonInput.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const parsed = JSON.parse(jsonInput);
      const payload = Array.isArray(parsed) ? parsed : [parsed];

      const resp = await apiFetch("/external-attention/import", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => null);
        throw new Error(body?.detail || `HTTP ${resp.status}`);
      }
      setResult(await resp.json());
    } catch (e: any) {
      setError(e.message || "Import failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 p-5">
      <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100 mb-3">
        {t("page.external_attention.import_title")}
      </h3>
      <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-4">
        {t("page.external_attention.import_description")}
      </p>

      {/* Mode toggle */}
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setMode("csv")}
          className={`px-3 py-1.5 text-sm rounded-md font-medium transition ${
            mode === "csv"
              ? "bg-indigo-600 text-white"
              : "bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700"
          }`}
        >
          {t("page.external_attention.mode_csv")}
        </button>
        <button
          onClick={() => setMode("json")}
          className={`px-3 py-1.5 text-sm rounded-md font-medium transition ${
            mode === "json"
              ? "bg-indigo-600 text-white"
              : "bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700"
          }`}
        >
          {t("page.external_attention.mode_json")}
        </button>
      </div>

      {mode === "csv" && (
        <div className="space-y-3">
          <div className="text-xs text-zinc-500 dark:text-zinc-400 font-mono bg-zinc-50 dark:bg-zinc-800 rounded p-2">
            {t("page.external_attention.csv_columns")}
          </div>
          <input
            ref={fileRef}
            type="file"
            accept=".csv,text/csv"
            className="block w-full text-sm text-zinc-600 dark:text-zinc-300
              file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0
              file:text-sm file:font-medium file:bg-indigo-50 file:text-indigo-700
              dark:file:bg-indigo-900/30 dark:file:text-indigo-300
              hover:file:bg-indigo-100 dark:hover:file:bg-indigo-900/50
              file:cursor-pointer cursor-pointer"
          />
          <button
            onClick={handleCSVUpload}
            disabled={loading}
            className="px-4 py-2 text-sm font-medium rounded-md bg-indigo-600 text-white
              hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {loading ? t("page.external_attention.importing") : t("page.external_attention.upload_csv")}
          </button>
        </div>
      )}

      {mode === "json" && (
        <div className="space-y-3">
          <textarea
            value={jsonInput}
            onChange={(e) => setJsonInput(e.target.value)}
            placeholder={`[\n  {\n    "entity_id": 1,\n    "source_type": "news",\n    "mention_count": 3,\n    "last_seen_at": "2026-05-10T00:00:00Z",\n    "title": "Article Title",\n    "url": "https://...",\n    "snippet": "Brief excerpt..."\n  }\n]`}
            rows={8}
            className="w-full rounded-md border border-zinc-300 dark:border-zinc-600
              bg-zinc-50 dark:bg-zinc-800 text-sm text-zinc-800 dark:text-zinc-200
              font-mono p-3 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500
              placeholder:text-zinc-400 dark:placeholder:text-zinc-500"
          />
          <button
            onClick={handleJSONImport}
            disabled={loading}
            className="px-4 py-2 text-sm font-medium rounded-md bg-indigo-600 text-white
              hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {loading ? t("page.external_attention.importing") : t("page.external_attention.import_json")}
          </button>
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="mt-4 rounded-md bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 p-3">
          <p className="text-sm font-medium text-emerald-800 dark:text-emerald-300">
            {t("page.external_attention.success_title")}
          </p>
          <ul className="mt-1 text-sm text-emerald-700 dark:text-emerald-400 space-y-0.5">
            <li>{t("page.external_attention.result_imported", { count: result.imported })}</li>
            <li>{t("page.external_attention.result_entities", { count: result.entities_updated })}</li>
            {result.skipped > 0 && (
              <li>{t("page.external_attention.result_skipped", { count: result.skipped })}</li>
            )}
          </ul>
          {result.warnings.length > 0 && (
            <details className="mt-2">
              <summary className="text-xs text-amber-700 dark:text-amber-400 cursor-pointer">
                {t("page.external_attention.warnings_label", { count: result.warnings.length })}
              </summary>
              <ul className="mt-1 text-xs text-amber-600 dark:text-amber-500 space-y-0.5 ml-3">
                {result.warnings.slice(0, 20).map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mt-4 rounded-md bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 p-3">
          <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
        </div>
      )}
    </div>
  );
}
