"use client";

import { useCallback, useEffect, useState } from "react";
import { useLanguage } from "../contexts/LanguageContext";
import { Badge, SectionHeader, type ToastVariant } from "../components/ui";
import { apiFetch } from "@/lib/api";

type SecretsCheck = {
    id: string;
    status: "ok" | "warning" | "critical" | string;
    summary: string;
    details: {
        jwt_insecure_default?: boolean;
        encryption_key_configured?: boolean;
        encryption_retiring_keys_present?: boolean;
        jwt_retiring_keys_present?: boolean;
        stale_rotations?: string[];
        max_age_days?: number;
    };
};

type RotationEvent = {
    id: number;
    secret_name: string;
    rotated_at: string;
    operator: string;
    rows_reencrypted: number | null;
    old_key_fingerprint: string | null;
    new_key_fingerprint: string | null;
    notes: string | null;
};

type Overview = { check: SecretsCheck; events: RotationEvent[] };

const STATUS_VARIANT: Record<string, "success" | "warning" | "error" | "default"> = {
    ok: "success",
    warning: "warning",
    critical: "error",
};

function getErrorMessage(error: unknown, fallback: string) {
    return error instanceof Error ? error.message : fallback;
}

export default function SecurityTab({ toast }: { toast: (msg: string, v?: ToastVariant) => void }) {
    const { t } = useLanguage();
    const [data, setData] = useState<Overview | null>(null);
    const [loading, setLoading] = useState(true);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const res = await apiFetch("/ops/secrets");
            if (!res.ok) {
                const body = await res.json().catch(() => ({ detail: t("settings.security.load_error") })) as { detail?: string };
                throw new Error(body.detail || t("settings.security.load_error"));
            }
            setData(await res.json() as Overview);
        } catch (error: unknown) {
            toast(getErrorMessage(error, t("settings.security.load_error")), "error");
        } finally {
            setLoading(false);
        }
    }, [t, toast]);

    useEffect(() => { void load(); }, [load]);

    const check = data?.check;
    const details = check?.details ?? {};
    const yn = (v: boolean | undefined) => (v ? t("settings.security.yes") : t("settings.security.no"));

    return (
        <div className="space-y-4">
            <SectionHeader title={t("settings.security.title")} description={t("settings.security.subtitle")} />
            {/* Status card */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                <div className="mb-4 flex items-center justify-between">
                    <h3 className="text-base font-semibold text-gray-900 dark:text-white">{t("settings.security.status_title")}</h3>
                    <div className="flex items-center gap-3">
                        {check && (
                            <Badge variant={STATUS_VARIANT[check.status] ?? "default"} dot>
                                {check.status.toUpperCase()}
                            </Badge>
                        )}
                        <button
                            onClick={() => void load()}
                            disabled={loading}
                            aria-busy={loading}
                            className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
                        >
                            {t("settings.security.refresh")}
                        </button>
                    </div>
                </div>

                {check && <p className="mb-4 text-sm font-medium text-gray-800 dark:text-gray-200">{check.summary}</p>}

                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <DetailRow label={t("settings.security.detail.jwt_default")}
                        value={details.jwt_insecure_default
                            ? t("settings.security.detail.jwt_default.insecure")
                            : t("settings.security.detail.jwt_default.secure")}
                        danger={details.jwt_insecure_default} />
                    <DetailRow label={t("settings.security.detail.enc_key")} value={yn(details.encryption_key_configured)} />
                    <DetailRow label={t("settings.security.detail.enc_retiring")} value={yn(details.encryption_retiring_keys_present)} />
                    <DetailRow label={t("settings.security.detail.jwt_retiring")} value={yn(details.jwt_retiring_keys_present)} />
                    <DetailRow label={t("settings.security.detail.stale")}
                        value={(details.stale_rotations && details.stale_rotations.length)
                            ? details.stale_rotations.join(", ")
                            : t("settings.security.detail.none")}
                        danger={!!(details.stale_rotations && details.stale_rotations.length)} />
                    <DetailRow label={t("settings.security.detail.cadence")} value={String(details.max_age_days ?? "—")} />
                </div>

                <p className="mt-4 text-xs text-gray-400">{t("settings.security.runbook")}</p>
            </div>

            {/* Evidence table */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                <h3 className="mb-4 text-base font-semibold text-gray-900 dark:text-white">{t("settings.security.evidence_title")}</h3>
                {!data || data.events.length === 0 ? (
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                        {loading && !data ? "…" : t("settings.security.empty")}
                    </p>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm">
                            <thead>
                                <tr className="border-b border-gray-200 text-xs uppercase tracking-wider text-gray-400 dark:border-gray-800">
                                    <th scope="col" className="py-2 pr-4">{t("settings.security.col.date")}</th>
                                    <th scope="col" className="py-2 pr-4">{t("settings.security.col.secret")}</th>
                                    <th scope="col" className="py-2 pr-4">{t("settings.security.col.operator")}</th>
                                    <th scope="col" className="py-2 pr-4">{t("settings.security.col.rows")}</th>
                                    <th scope="col" className="py-2 pr-4">{t("settings.security.col.fingerprints")}</th>
                                    <th scope="col" className="py-2">{t("settings.security.col.notes")}</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.events.map(ev => (
                                    <tr key={ev.id} className="border-b border-gray-100 text-gray-700 dark:border-gray-800/60 dark:text-gray-300">
                                        <td className="py-2 pr-4 whitespace-nowrap">{new Date(ev.rotated_at).toLocaleString()}</td>
                                        <td className="py-2 pr-4 font-mono text-xs">{ev.secret_name}</td>
                                        <td className="py-2 pr-4">{ev.operator}</td>
                                        <td className="py-2 pr-4">{ev.rows_reencrypted ?? "—"}</td>
                                        <td className="py-2 pr-4 font-mono text-[11px] text-gray-500">
                                            {(ev.old_key_fingerprint ?? "—") + " → " + (ev.new_key_fingerprint ?? "—")}
                                        </td>
                                        <td className="py-2 text-gray-500">{ev.notes ?? "—"}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
}

function DetailRow({ label, value, danger }: { label: string; value: string; danger?: boolean }) {
    return (
        <div className="flex items-center justify-between rounded-xl border border-gray-100 bg-gray-50 px-4 py-3 dark:border-gray-800 dark:bg-gray-800/50">
            <span className="text-[11px] font-bold uppercase tracking-wider text-gray-400">{label}</span>
            <span className={`text-sm font-medium ${danger ? "text-red-600 dark:text-red-400" : "text-gray-800 dark:text-gray-200"}`}>{value}</span>
        </div>
    );
}
