"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useLanguage } from "../contexts/LanguageContext";
import type { ToastVariant } from "../components/ui";

type ResetPreview = {
  scope_type: string;
  scope_label: string;
  confirmation_text: string;
  counts: Record<string, number>;
  preserved: string[];
};

type ResetResult = {
  deleted: Record<string, number>;
  reset_counters: Record<string, number>;
};

function formatLabel(key: string) {
  return key.replace(/_/g, " ");
}

export default function WorkspaceResetTab({
  toast,
}: {
  toast: (msg: string, v?: ToastVariant) => void;
}) {
  const { t } = useLanguage();
  const tr = useCallback(
    (key: string, fallback: string) => {
      const value = t(key);
      return value === key ? fallback : value;
    },
    [t],
  );

  const [preview, setPreview] = useState<ResetPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [confirmationText, setConfirmationText] = useState("");
  const [lastResult, setLastResult] = useState<ResetResult | null>(null);

  useEffect(() => {
    let active = true;

    void (async () => {
      try {
        const response = await apiFetch("/admin/workspace-reset/preview");
        if (!response.ok) {
          throw new Error(tr("settings.workspace_reset.toast.load_failed", "Failed to load reset summary"));
        }
        const data = (await response.json()) as ResetPreview;
        if (!active) return;
        setPreview(data);
      } catch (error) {
        const message = error instanceof Error
          ? error.message
          : tr("settings.workspace_reset.toast.load_failed", "Failed to load reset summary");
        toast(message, "error");
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    })();

    return () => {
      active = false;
    };
  }, [toast, tr]);

  const confirmationToken = preview?.confirmation_text ?? "RESET";
  const canSubmit = confirmationText.trim().toUpperCase() === confirmationToken;

  const countEntries = useMemo(
    () => Object.entries(preview?.counts ?? {}).filter(([, value]) => value > 0),
    [preview],
  );

  const totalAffected = useMemo(
    () => countEntries.reduce((acc, [, value]) => acc + value, 0),
    [countEntries],
  );

  async function handleReset() {
    if (!canSubmit || !preview) {
      toast(tr("settings.workspace_reset.toast.confirmation_required", "Type the confirmation word before resetting"), "warning");
      return;
    }

    setSubmitting(true);
    try {
      const response = await apiFetch("/admin/workspace-reset", {
        method: "POST",
        body: JSON.stringify({ confirmation_text: confirmationText }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail ?? tr("settings.workspace_reset.toast.reset_failed", "Workspace reset failed"));
      }
      setLastResult(data as ResetResult);
      setConfirmationText("");

      const refreshed = await apiFetch("/admin/workspace-reset/preview");
      if (refreshed.ok) {
        setPreview((await refreshed.json()) as ResetPreview);
      }

      toast(tr("settings.workspace_reset.toast.reset_success", "Workspace data reset completed"), "success");
    } catch (error) {
      const message = error instanceof Error
        ? error.message
        : tr("settings.workspace_reset.toast.reset_failed", "Workspace reset failed");
      toast(message, "error");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <div className="py-10 text-center text-sm text-gray-400">{t("common.loading")}</div>;
  }

  if (!preview) {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900/30 dark:bg-red-900/10 dark:text-red-300">
        {tr("settings.workspace_reset.unavailable", "The workspace reset summary is not available right now.")}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-amber-200 bg-amber-50/80 p-4 shadow-sm dark:border-amber-900/30 dark:bg-amber-900/10">
        <p className="text-sm font-semibold text-amber-950 dark:text-amber-100">
          {tr("settings.workspace_reset.guidance_title", "Reset only the active workspace when you need a clean pilot state")}
        </p>
        <p className="mt-1 text-xs text-amber-900/80 dark:text-amber-200/80">
          {tr("settings.workspace_reset.guidance_body", "This removes imported and generated workspace data, but preserves users, organization membership, branding, notifications, and other platform settings.")}
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-500 dark:text-gray-400">
            {tr("settings.workspace_reset.summary.scope", "Active scope")}
          </p>
          <p className="mt-2 text-sm font-semibold text-gray-900 dark:text-white">{preview.scope_label}</p>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-500 dark:text-gray-400">
            {tr("settings.workspace_reset.summary.scope_type", "Scope type")}
          </p>
          <p className="mt-2 text-sm font-semibold text-gray-900 capitalize dark:text-white">{preview.scope_type}</p>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-500 dark:text-gray-400">
            {tr("settings.workspace_reset.summary.affected", "Affected rows")}
          </p>
          <p className="mt-2 text-sm font-semibold text-gray-900 dark:text-white">{totalAffected}</p>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.2fr,0.8fr]">
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <h3 className="text-base font-semibold text-gray-900 dark:text-white">
            {tr("settings.workspace_reset.impact_title", "Data that will be cleared")}
          </h3>
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
            {tr("settings.workspace_reset.impact_help", "The preview below reflects the active workspace only. Other organizations remain untouched.")}
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {countEntries.length ? (
              countEntries.map(([key, value]) => (
                <div key={key} className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-800 dark:bg-gray-950/40">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-500 dark:text-gray-400">
                    {tr(`settings.workspace_reset.count.${key}`, formatLabel(key))}
                  </p>
                  <p className="mt-2 text-sm font-semibold text-gray-900 dark:text-white">{value}</p>
                </div>
              ))
            ) : (
              <div className="rounded-xl border border-dashed border-gray-200 px-4 py-8 text-center dark:border-gray-800 sm:col-span-2">
                <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  {tr("settings.workspace_reset.empty", "This workspace is already clean.")}
                </p>
                <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                  {tr("settings.workspace_reset.empty_help", "No imported or generated records were found for the current scope.")}
                </p>
              </div>
            )}
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
            <h3 className="text-base font-semibold text-gray-900 dark:text-white">
              {tr("settings.workspace_reset.preserved_title", "What stays in place")}
            </h3>
            <ul className="mt-4 space-y-2 text-sm text-gray-600 dark:text-gray-300">
              {preview.preserved.map((item) => (
                <li key={item} className="flex items-start gap-2">
                  <span className="mt-1 h-1.5 w-1.5 rounded-full bg-emerald-500" />
                  <span>{tr(`settings.workspace_reset.preserved.${item.replace(/ /g, "_")}`, item)}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-2xl border border-red-200 bg-red-50 p-6 shadow-sm dark:border-red-900/30 dark:bg-red-900/10">
            <h3 className="text-base font-semibold text-red-900 dark:text-red-100">
              {tr("settings.workspace_reset.confirm_title", "Danger zone")}
            </h3>
            <p className="mt-1 text-xs text-red-800/80 dark:text-red-200/80">
              {tr("settings.workspace_reset.confirm_help", 'Type "{token}" to confirm. This action is intended for pilot clean-up and cannot be undone.',).replace("{token}", confirmationToken)}
            </p>
            <input
              value={confirmationText}
              onChange={(event) => setConfirmationText(event.target.value)}
              placeholder={confirmationToken}
              className="mt-4 h-10 w-full rounded-lg border border-red-200 bg-white px-3 text-sm text-gray-900 outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500 dark:border-red-900/40 dark:bg-gray-900 dark:text-white"
            />
            <button
              onClick={handleReset}
              disabled={submitting || !canSubmit}
              className="mt-4 inline-flex w-full items-center justify-center rounded-xl bg-red-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting
                ? tr("settings.workspace_reset.resetting", "Resetting workspace…")
                : tr("settings.workspace_reset.reset_button", "Reset workspace data")}
            </button>
          </div>
        </div>
      </div>

      {lastResult && (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50/80 p-4 shadow-sm dark:border-emerald-900/30 dark:bg-emerald-900/10">
          <p className="text-sm font-semibold text-emerald-950 dark:text-emerald-100">
            {tr("settings.workspace_reset.result_title", "Last reset completed")}
          </p>
          <p className="mt-1 text-xs text-emerald-900/80 dark:text-emerald-200/80">
            {tr("settings.workspace_reset.result_help", "The workspace is back to a clean starting point for new imports, demo runs, or stakeholder sessions.")}
          </p>
        </div>
      )}
    </div>
  );
}
