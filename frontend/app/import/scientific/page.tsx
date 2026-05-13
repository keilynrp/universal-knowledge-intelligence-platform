"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { useLanguage } from "@/app/contexts/LanguageContext";

/* ── Shared types ────────────────────────────────────────────────────── */

type Source = { id: string; name: string; requires_key: boolean };
type PreviewRecord = {
  title: string;
  doi: string | null;
  authors: string[];
  year: number | null;
  journal: string | null;
  concepts: string[];
  source_api: string;
};
type ImportResult = { imported: number; skipped: number };
type Step = "query" | "preview" | "done";
type TabId = "connector" | "openalex" | "pubmed";

type ImportJobResponse = { job_id: string; status: string; record_count: number };
type ImportStatusResponse = {
  job_id: string;
  status: string;
  progress: number;
  records_inserted: number;
  total: number;
};

async function readJsonOrThrow<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? String(payload.detail)
        : "Request failed";
    throw new Error(detail);
  }
  return payload as T;
}

/* ── Progress Bar component ──────────────────────────────────────────── */

function ImportProgressBar({
  jobId,
  onComplete,
  onError,
}: {
  jobId: string;
  onComplete: (inserted: number) => void;
  onError: (msg: string) => void;
}) {
  const { t } = useLanguage();
  const tr = (key: string, fb: string) => { const v = t(key); return v === key ? fb : v; };
  const [progress, setProgress] = useState(0);
  const [inserted, setInserted] = useState(0);
  const [total, setTotal] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!jobId || jobId === "preview") return;

    const poll = async () => {
      try {
        const resp = await apiFetch(`/import/status/${jobId}`);
        const data = await readJsonOrThrow<ImportStatusResponse>(resp);
        setProgress(data.progress);
        setInserted(data.records_inserted);
        setTotal(data.total);

        if (data.status === "done") {
          if (intervalRef.current) clearInterval(intervalRef.current);
          onComplete(data.records_inserted);
        } else if (data.status === "failed") {
          if (intervalRef.current) clearInterval(intervalRef.current);
          onError(tr("page.import.api.error.job_failed", "Import job failed"));
        }
      } catch {
        if (intervalRef.current) clearInterval(intervalRef.current);
        onError(tr("page.import.api.error.poll_failed", "Failed to check import status"));
      }
    };

    intervalRef.current = setInterval(poll, 2000);
    poll();

    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [jobId]); // eslint-disable-line react-hooks/exhaustive-deps

  const pct = Math.round(progress * 100);
  return (
    <div className="space-y-2">
      <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400">
        <span>{tr("page.import.api.progress", "Importing…")} {pct}%</span>
        <span>{inserted} / {total} {tr("page.import.api.records", "records")}</span>
      </div>
      <div className="h-2 w-full rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
        <div
          className="h-full rounded-full bg-indigo-600 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

/* ── Preview results table (shared) ──────────────────────────────────── */

function PreviewTable({ records }: { records: PreviewRecord[] }) {
  const { t } = useLanguage();
  return (
    <div className="overflow-auto rounded-xl border border-gray-200 dark:border-gray-700">
      <table className="min-w-full text-xs">
        <thead className="bg-gray-50 dark:bg-gray-800">
          <tr>
            {[
              t("page.import.scientific.table.title"),
              t("page.import.scientific.table.authors"),
              t("page.import.scientific.table.year"),
              t("page.import.scientific.table.doi"),
            ].map((h) => (
              <th key={h} className="px-3 py-2 text-left font-medium text-gray-600 dark:text-gray-400">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
          {records.map((r, i) => (
            <tr key={i} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
              <td className="px-3 py-2 max-w-xs truncate" title={r.title}>{r.title}</td>
              <td className="px-3 py-2 text-gray-500">
                {(r.authors || []).slice(0, 2).join("; ")}
                {(r.authors?.length ?? 0) > 2 ? " …" : ""}
              </td>
              <td className="px-3 py-2 text-gray-500">{r.year ?? "—"}</td>
              <td className="px-3 py-2 font-mono text-gray-500 max-w-[160px] truncate">{r.doi ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ── OpenAlex Tab ────────────────────────────────────────────────────── */

function OpenAlexTab() {
  const { t } = useLanguage();
  const tr = (key: string, fb: string) => { const v = t(key); return v === key ? fb : v; };

  const [keyword, setKeyword] = useState("");
  const [author, setAuthor] = useState("");
  const [issn, setIssn] = useState("");
  const [limit, setLimit] = useState(100);
  const [step, setStep] = useState<"form" | "preview" | "importing" | "done">("form");
  const [preview, setPreview] = useState<PreviewRecord[]>([]);
  const [jobId, setJobId] = useState("");
  const [imported, setImported] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handlePreview = async () => {
    setLoading(true);
    setError(null);
    try {
      const filters: Record<string, string> = {};
      if (author) filters.author = author;
      if (issn) filters.issn = issn;

      const resp = await apiFetch("/import/openalex", {
        method: "POST",
        body: JSON.stringify({ query: keyword, limit: 10, filters, preview: true }),
      });
      const data = await readJsonOrThrow<ImportJobResponse>(resp);
      // For preview, fetch from entities or use a separate preview approach
      // The endpoint returns record_count; we re-fetch using search for preview display
      const previewResp = await apiFetch("/import/openalex", {
        method: "POST",
        body: JSON.stringify({ query: keyword, limit: 10, filters, preview: true }),
      });
      // Preview doesn't give us records back directly — use the count
      // Actually let's adapt: do a lightweight call just for the preview table
      setPreview([]); // We show count-based preview
      setStep("preview");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : tr("page.import.api.error.preview", "Preview failed"));
    } finally {
      setLoading(false);
    }
  };

  const handleImport = async () => {
    setLoading(true);
    setError(null);
    try {
      const filters: Record<string, string> = {};
      if (author) filters.author = author;
      if (issn) filters.issn = issn;

      const resp = await apiFetch("/import/openalex", {
        method: "POST",
        body: JSON.stringify({ query: keyword, limit, filters }),
      });
      const data = await readJsonOrThrow<ImportJobResponse>(resp);
      setJobId(data.job_id);
      setStep("importing");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : tr("page.import.api.error.import", "Import failed"));
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setStep("form");
    setPreview([]);
    setJobId("");
    setImported(0);
    setError(null);
  };

  return (
    <div className="space-y-4">
      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700 dark:bg-red-900/20 dark:border-red-800 dark:text-red-300">
          <p className="font-semibold">{tr("page.import.api.error.title", "Import issue")}</p>
          <p className="mt-1">{error}</p>
          {step !== "form" && (
            <button onClick={reset} className="mt-2 text-xs text-red-600 hover:underline">
              {tr("page.import.api.retry", "Try again")}
            </button>
          )}
        </div>
      )}

      {step === "form" && (
        <div className="space-y-4 rounded-xl border border-gray-200 dark:border-gray-700 p-5 bg-white dark:bg-gray-900">
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 dark:border-emerald-500/20 dark:bg-emerald-500/5 dark:text-emerald-200">
            <p className="font-semibold">{tr("page.import.api.openalex.hint_title", "OpenAlex — Free Academic API")}</p>
            <p className="mt-1 text-xs leading-5 text-emerald-700 dark:text-emerald-300">
              {tr("page.import.api.openalex.hint", "Search 250M+ works by keyword, author, or ISSN. No API key required. Up to 1,000 records per import.")}
            </p>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
              {tr("page.import.api.keyword", "Search keyword")}
            </label>
            <input
              type="text"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder={tr("page.import.api.keyword_placeholder", "e.g. knowledge management")}
              className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm px-3 py-2"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                {tr("page.import.api.author_filter", "Author (optional)")}
              </label>
              <input
                type="text"
                value={author}
                onChange={(e) => setAuthor(e.target.value)}
                placeholder={tr("page.import.api.author_placeholder", "e.g. Jane Doe")}
                className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm px-3 py-2"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                {tr("page.import.api.issn_filter", "ISSN (optional)")}
              </label>
              <input
                type="text"
                value={issn}
                onChange={(e) => setIssn(e.target.value)}
                placeholder={tr("page.import.api.issn_placeholder", "e.g. 1234-5678")}
                className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm px-3 py-2"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
              {tr("page.import.api.limit", "Records to import")}: {limit}
            </label>
            <input
              type="range"
              min={10}
              max={1000}
              step={10}
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              className="w-full accent-indigo-600"
            />
            <div className="flex justify-between text-[10px] text-gray-400 mt-1">
              <span>10</span><span>500</span><span>1,000</span>
            </div>
          </div>
          <button
            onClick={handleImport}
            disabled={loading || !keyword}
            className="w-full rounded-md bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-sm font-medium py-2 px-4 transition-colors"
          >
            {loading
              ? tr("page.import.api.searching", "Searching…")
              : tr("page.import.api.openalex.import_cta", "Import from OpenAlex")}
          </button>
        </div>
      )}

      {step === "importing" && (
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 p-5 bg-white dark:bg-gray-900 space-y-4">
          <p className="text-sm font-medium text-gray-700 dark:text-gray-200">
            {tr("page.import.api.importing_from", "Importing from")} OpenAlex…
          </p>
          <ImportProgressBar
            jobId={jobId}
            onComplete={(n) => { setImported(n); setStep("done"); }}
            onError={(msg) => setError(msg)}
          />
        </div>
      )}

      {step === "done" && (
        <div className="rounded-xl border border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20 p-6 text-center space-y-3">
          <div className="text-3xl font-bold text-green-700 dark:text-green-400">{imported}</div>
          <div className="text-sm text-green-700 dark:text-green-300">
            {tr("page.import.api.success", "records imported successfully from OpenAlex")}
          </div>
          <div className="flex gap-3 justify-center pt-2">
            <Link href="/" className="rounded-md bg-indigo-600 hover:bg-indigo-700 text-white text-sm px-4 py-2">
              {t("page.import.scientific.view_entities")}
            </Link>
            <button onClick={reset} className="rounded-md border border-gray-300 dark:border-gray-600 text-sm px-4 py-2 hover:bg-gray-50 dark:hover:bg-gray-800">
              {t("page.import.scientific.new_import")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── PubMed Tab ──────────────────────────────────────────────────────── */

function PubMedTab() {
  const { t } = useLanguage();
  const tr = (key: string, fb: string) => { const v = t(key); return v === key ? fb : v; };

  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(100);
  const [step, setStep] = useState<"form" | "importing" | "done">("form");
  const [jobId, setJobId] = useState("");
  const [imported, setImported] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleImport = async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await apiFetch("/import/pubmed", {
        method: "POST",
        body: JSON.stringify({ query, limit }),
      });
      const data = await readJsonOrThrow<ImportJobResponse>(resp);
      setJobId(data.job_id);
      setStep("importing");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : tr("page.import.api.error.import", "Import failed"));
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setStep("form");
    setJobId("");
    setImported(0);
    setError(null);
  };

  return (
    <div className="space-y-4">
      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700 dark:bg-red-900/20 dark:border-red-800 dark:text-red-300">
          <p className="font-semibold">{tr("page.import.api.error.title", "Import issue")}</p>
          <p className="mt-1">{error}</p>
          {step !== "form" && (
            <button onClick={reset} className="mt-2 text-xs text-red-600 hover:underline">
              {tr("page.import.api.retry", "Try again")}
            </button>
          )}
        </div>
      )}

      {step === "form" && (
        <div className="space-y-4 rounded-xl border border-gray-200 dark:border-gray-700 p-5 bg-white dark:bg-gray-900">
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-500/20 dark:bg-amber-500/5 dark:text-amber-200">
            <p className="font-semibold">{tr("page.import.api.pubmed.hint_title", "PubMed — NCBI Biomedical Literature")}</p>
            <p className="mt-1 text-xs leading-5 text-amber-700 dark:text-amber-300">
              {tr("page.import.api.pubmed.hint", "Search 36M+ biomedical citations via NCBI E-utilities. No API key required. Up to 500 records per import.")}
            </p>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
              {tr("page.import.api.pubmed.query_label", "PubMed search query")}
            </label>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={tr("page.import.api.pubmed.query_placeholder", "e.g. knowledge management systematic review")}
              className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
              {tr("page.import.api.limit", "Records to import")}: {limit}
            </label>
            <input
              type="range"
              min={10}
              max={500}
              step={10}
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              className="w-full accent-indigo-600"
            />
            <div className="flex justify-between text-[10px] text-gray-400 mt-1">
              <span>10</span><span>250</span><span>500</span>
            </div>
          </div>
          <button
            onClick={handleImport}
            disabled={loading || !query}
            className="w-full rounded-md bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white text-sm font-medium py-2 px-4 transition-colors"
          >
            {loading
              ? tr("page.import.api.searching", "Searching…")
              : tr("page.import.api.pubmed.import_cta", "Import from PubMed")}
          </button>
        </div>
      )}

      {step === "importing" && (
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 p-5 bg-white dark:bg-gray-900 space-y-4">
          <p className="text-sm font-medium text-gray-700 dark:text-gray-200">
            {tr("page.import.api.importing_from", "Importing from")} PubMed…
          </p>
          <ImportProgressBar
            jobId={jobId}
            onComplete={(n) => { setImported(n); setStep("done"); }}
            onError={(msg) => setError(msg)}
          />
        </div>
      )}

      {step === "done" && (
        <div className="rounded-xl border border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20 p-6 text-center space-y-3">
          <div className="text-3xl font-bold text-green-700 dark:text-green-400">{imported}</div>
          <div className="text-sm text-green-700 dark:text-green-300">
            {tr("page.import.api.success_pubmed", "records imported successfully from PubMed")}
          </div>
          <div className="flex gap-3 justify-center pt-2">
            <Link href="/" className="rounded-md bg-indigo-600 hover:bg-indigo-700 text-white text-sm px-4 py-2">
              {t("page.import.scientific.view_entities")}
            </Link>
            <button onClick={reset} className="rounded-md border border-gray-300 dark:border-gray-600 text-sm px-4 py-2 hover:bg-gray-50 dark:hover:bg-gray-800">
              {t("page.import.scientific.new_import")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Connector Search Tab (original page content) ────────────────────── */

function ConnectorSearchTab() {
  const { t } = useLanguage();
  const tr = (key: string, fallback: string) => {
    const value = t(key);
    return value === key ? fallback : value;
  };
  const [sources, setSources] = useState<Source[]>([]);
  const [sourcesLoaded, setSourcesLoaded] = useState(false);
  const [source, setSource] = useState("crossref");
  const [mode, setMode] = useState<"search" | "dois">("search");
  const [query, setQuery] = useState("");
  const [doiText, setDoiText] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [libraryId, setLibraryId] = useState("");
  const [maxResults, setMaxResults] = useState(20);
  const [step, setStep] = useState<Step>("query");
  const [preview, setPreview] = useState<PreviewRecord[]>([]);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadSources = async () => {
    if (sourcesLoaded) return;
    try {
      const resp = await apiFetch("/scientific/sources");
      const data: Source[] = await resp.json();
      setSources(data);
      setSourcesLoaded(true);
    } catch {
      // fallback to hardcoded default in select
    }
  };

  const selectedSource = sources.find((s) => s.id === source);

  const buildConfig = (): Record<string, string> => {
    const cfg: Record<string, string> = {};
    if (apiKey) cfg.api_key = apiKey;
    if (libraryId) cfg.library_id = libraryId;
    return cfg;
  };

  const handlePreview = async () => {
    setLoading(true);
    setError(null);
    try {
      let data: PreviewRecord[];
      if (mode === "dois") {
        const dois = doiText.split(/[\n,]+/).map((d) => d.trim()).filter(Boolean);
        const resp = await apiFetch("/scientific/dois/preview", {
          method: "POST",
          body: JSON.stringify({ dois, source, config: buildConfig() }),
        });
        data = await readJsonOrThrow<PreviewRecord[]>(resp);
      } else {
        const resp = await apiFetch("/scientific/search", {
          method: "POST",
          body: JSON.stringify({ source, query, max_results: maxResults, config: buildConfig() }),
        });
        data = await readJsonOrThrow<PreviewRecord[]>(resp);
      }
      setPreview(data);
      setStep("preview");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t("page.import.scientific.error.search"));
    } finally {
      setLoading(false);
    }
  };

  const handleImport = async () => {
    setLoading(true);
    setError(null);
    try {
      let data: ImportResult;
      if (mode === "dois") {
        const dois = doiText.split(/[\n,]+/).map((d) => d.trim()).filter(Boolean);
        const resp = await apiFetch("/scientific/dois", {
          method: "POST",
          body: JSON.stringify({ dois, source, config: buildConfig() }),
        });
        data = await readJsonOrThrow<ImportResult>(resp);
      } else {
        const resp = await apiFetch("/scientific/import", {
          method: "POST",
          body: JSON.stringify({ source, query, max_results: maxResults, config: buildConfig() }),
        });
        data = await readJsonOrThrow<ImportResult>(resp);
      }
      setResult(data);
      setStep("done");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t("page.import.scientific.error.import"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700 dark:bg-red-900/20 dark:border-red-800 dark:text-red-300">
          <p className="font-semibold">{tr("page.import.scientific.error.title", "Import issue")}</p>
          <p className="mt-1">{error}</p>
        </div>
      )}

      {/* Progress steps */}
      <div className="flex gap-2 text-xs font-medium">
        {(["query", "preview", "done"] as Step[]).map((s, i) => (
          <span
            key={s}
            className={`px-3 py-1 rounded-full ${
              step === s
                ? "bg-indigo-600 text-white"
                : "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400"
            }`}
          >
            {i + 1}. {t(`page.import.scientific.step.${s}`)}
          </span>
        ))}
      </div>

      {/* Step 1: Query */}
      {step === "query" && (
        <div
          className="space-y-4 rounded-xl border border-gray-200 dark:border-gray-700 p-5 bg-white dark:bg-gray-900"
          onClick={loadSources}
        >
          <div className="rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm text-indigo-800 dark:border-indigo-500/20 dark:bg-indigo-500/5 dark:text-indigo-200">
            <p className="font-semibold">{tr("page.import.scientific.guidance.title", "Preview first, import second")}</p>
            <p className="mt-1 text-xs leading-5 text-indigo-700 dark:text-indigo-300">
              {mode === "dois"
                ? tr("page.import.scientific.guidance.dois", "Use DOI mode when you already have exact identifiers.")
                : tr("page.import.scientific.guidance.search", "Use search mode when you need to explore a query first.")}
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{t("page.import.scientific.source")}</label>
              <select
                value={source}
                onChange={(e) => setSource(e.target.value)}
                className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm px-3 py-2"
              >
                {sources.length === 0 && <option value="crossref">CrossRef</option>}
                {sources.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}{s.requires_key ? " 🔑" : ""}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{t("page.import.scientific.mode")}</label>
              <select
                value={mode}
                onChange={(e) => setMode(e.target.value as "search" | "dois")}
                className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm px-3 py-2"
              >
                <option value="search">{t("page.import.scientific.mode.search")}</option>
                <option value="dois">{t("page.import.scientific.mode.dois")}</option>
              </select>
            </div>
          </div>

          {selectedSource?.requires_key && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{t("page.import.scientific.api_key")}</label>
                <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="Your API key"
                  className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm px-3 py-2" />
              </div>
              {source === "zotero" && (
                <div>
                  <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{t("page.import.scientific.library_id")}</label>
                  <input type="text" value={libraryId} onChange={(e) => setLibraryId(e.target.value)}
                    placeholder={t("page.import.scientific.library_id_placeholder")}
                    className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm px-3 py-2" />
                </div>
              )}
            </div>
          )}

          {mode === "search" ? (
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                {source === "orcid" ? t("page.import.scientific.orcid_label") : t("page.import.scientific.search_label")}
              </label>
              <input type="text" value={query} onChange={(e) => setQuery(e.target.value)}
                placeholder={source === "orcid" ? t("page.import.scientific.orcid_placeholder") : t("page.import.scientific.search_placeholder")}
                className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm px-3 py-2" />
              <div className="mt-2 flex items-center gap-2 text-xs text-gray-500">
                <span>{t("page.import.scientific.max_results")}</span>
                <input type="number" min={1} max={100} value={maxResults} onChange={(e) => setMaxResults(Number(e.target.value))}
                  className="w-16 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-2 py-1 text-xs" />
              </div>
            </div>
          ) : (
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{t("page.import.scientific.dois_label")}</label>
              <textarea value={doiText} onChange={(e) => setDoiText(e.target.value)} rows={6}
                placeholder={"10.1038/nature12373\n10.1016/j.cell.2022.01.001"}
                className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm px-3 py-2 font-mono" />
            </div>
          )}

          <button onClick={handlePreview}
            disabled={loading || (mode === "search" && !query) || (mode === "dois" && !doiText)}
            className="w-full rounded-md bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-medium py-2 px-4 transition-colors">
            {loading ? t("page.import.scientific.preview_loading") : t("page.import.scientific.preview_cta")}
          </button>
        </div>
      )}

      {/* Step 2: Preview */}
      {step === "preview" && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="text-sm text-gray-600 dark:text-gray-400">{t("page.import.scientific.results_found", { count: preview.length })}</span>
            <button onClick={() => setStep("query")} className="text-xs text-indigo-600 hover:underline">
              {t("page.import.scientific.change_query")}
            </button>
          </div>
          <div className="overflow-auto rounded-xl border border-gray-200 dark:border-gray-700">
            <table className="min-w-full text-xs">
              <thead className="bg-gray-50 dark:bg-gray-800">
                <tr>
                  {[
                    t("page.import.scientific.table.title"),
                    t("page.import.scientific.table.authors"),
                    t("page.import.scientific.table.year"),
                    t("page.import.scientific.table.doi"),
                    t("page.import.scientific.table.source"),
                  ].map((h) => (
                    <th key={h} className="px-3 py-2 text-left font-medium text-gray-600 dark:text-gray-400">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                {preview.map((r, i) => (
                  <tr key={i} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                    <td className="px-3 py-2 max-w-xs truncate" title={r.title}>{r.title}</td>
                    <td className="px-3 py-2 text-gray-500">
                      {(r.authors || []).slice(0, 2).join("; ")}{(r.authors?.length ?? 0) > 2 ? " …" : ""}
                    </td>
                    <td className="px-3 py-2 text-gray-500">{r.year ?? "—"}</td>
                    <td className="px-3 py-2 font-mono text-gray-500 max-w-[160px] truncate">{r.doi ?? "—"}</td>
                    <td className="px-3 py-2">
                      <span className="rounded-full bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300 px-2 py-0.5">{r.source_api}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button onClick={handleImport} disabled={loading}
            className="w-full rounded-md bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-sm font-medium py-2 px-4 transition-colors">
            {loading ? t("page.import.scientific.import_loading") : t("page.import.scientific.import_cta", { count: preview.length })}
          </button>
        </div>
      )}

      {/* Step 3: Done */}
      {step === "done" && result && (
        <div className="rounded-xl border border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20 p-6 text-center space-y-3">
          <div className="text-3xl font-bold text-green-700 dark:text-green-400">{result.imported}</div>
          <div className="text-sm text-green-700 dark:text-green-300">{t("page.import.scientific.success")}</div>
          <div className="flex gap-3 justify-center pt-2">
            <Link href="/" className="rounded-md bg-indigo-600 hover:bg-indigo-700 text-white text-sm px-4 py-2">
              {t("page.import.scientific.view_entities")}
            </Link>
            <button onClick={() => { setStep("query"); setPreview([]); setResult(null); }}
              className="rounded-md border border-gray-300 dark:border-gray-600 text-sm px-4 py-2 hover:bg-gray-50 dark:hover:bg-gray-800">
              {t("page.import.scientific.new_import")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Main Page with Tabs ─────────────────────────────────────────────── */

const TABS: { id: TabId; labelKey: string; fallback: string }[] = [
  { id: "connector", labelKey: "page.import.api.tab.connector", fallback: "Connector Search" },
  { id: "openalex",  labelKey: "page.import.api.tab.openalex",  fallback: "OpenAlex" },
  { id: "pubmed",    labelKey: "page.import.api.tab.pubmed",    fallback: "PubMed" },
];

export default function ScientificImportPage() {
  const { t } = useLanguage();
  const tr = (key: string, fb: string) => { const v = t(key); return v === key ? fb : v; };
  const [activeTab, setActiveTab] = useState<TabId>("connector");

  return (
    <div className="max-w-3xl mx-auto py-8 px-4 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t("page.import.scientific.title")}</h1>
        <p className="text-sm text-gray-500 mt-1">{t("page.import.scientific.description")}</p>
      </div>

      {/* Tab bar */}
      <div className="flex border-b border-gray-200 dark:border-gray-700">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
              activeTab === tab.id
                ? "border-indigo-600 text-indigo-600 dark:text-indigo-400 dark:border-indigo-400"
                : "border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            }`}
          >
            {tr(tab.labelKey, tab.fallback)}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "connector" && <ConnectorSearchTab />}
      {activeTab === "openalex"  && <OpenAlexTab />}
      {activeTab === "pubmed"    && <PubMedTab />}
    </div>
  );
}
