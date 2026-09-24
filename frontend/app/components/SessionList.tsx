"use client";

import { useCallback, useEffect, useState } from "react";
import { useLanguage } from "../contexts/LanguageContext";
import { Badge, Button, ErrorBanner, type ToastVariant } from "./ui";
import { apiFetch } from "@/lib/api";
import { formatDateTime, formatRelativeTime } from "../lib/dateFormat";
import { describeUserAgent } from "../lib/userAgent";

export type SessionItem = {
    id: number;
    sid: string;
    created_at: string | null;
    last_seen_at: string | null;
    expires_at: string | null;
    user_agent: string | null;
    ip_address: string | null;
    current: boolean;
};

/**
 * The live sessions behind one account, each revocable on its own.
 *
 * `endpoint` is the list URL; revoking one session is `DELETE endpoint/{id}`
 * and revoking in bulk is `DELETE endpoint`, which is the shape of both
 * `/auth/sessions` (your own) and `/users/{id}/sessions` (super_admin). The
 * backend decides what bulk means: your own list keeps the session making the
 * request, an admin list revokes everything.
 *
 * The session this browser is using is marked and has no revoke button.
 * Revoking it would be a sign-out that looks like something else, and on a
 * phone in the middle of an incident that is the wrong button to make easy.
 * Every destructive action asks for confirmation inline rather than through
 * `confirm()`, which is easy to dismiss by accident on a touch screen.
 */
export default function SessionList({
    endpoint,
    scope,
    username,
    toast,
}: {
    endpoint: string;
    scope: "self" | "admin";
    username?: string;
    toast: (msg: string, v?: ToastVariant) => void;
}) {
    const { t, language } = useLanguage();
    const [items, setItems] = useState<SessionItem[] | null>(null);
    const [loadError, setLoadError] = useState(false);
    const [confirming, setConfirming] = useState<number | "all" | null>(null);
    const [busy, setBusy] = useState<number | "all" | null>(null);

    const load = useCallback(async () => {
        setLoadError(false);
        try {
            const res = await apiFetch(endpoint);
            if (!res.ok) throw new Error(String(res.status));
            const body = await res.json() as { items: SessionItem[] };
            setItems(body.items);
        } catch {
            setLoadError(true);
        }
    }, [endpoint]);

    useEffect(() => { void load(); }, [load]);

    async function revoke(target: number | "all") {
        setBusy(target);
        try {
            const res = await apiFetch(target === "all" ? endpoint : `${endpoint}/${target}`, { method: "DELETE" });
            if (!res.ok) {
                const err = await res.json().catch(() => ({})) as { detail?: string };
                throw new Error(err.detail || t("sessions.toast.revoke_error"));
            }
            const { revoked } = await res.json() as { revoked: number };
            if (target !== "all") toast(t("sessions.toast.revoked"), "success");
            else if (revoked > 0) toast(t("sessions.toast.revoked_many", { count: revoked }), "success");
            else toast(t("sessions.toast.none"), "info");
        } catch (error: unknown) {
            toast(error instanceof Error ? error.message : t("sessions.toast.revoke_error"), "error");
        } finally {
            setBusy(null);
            setConfirming(null);
            await load();
        }
    }

    if (loadError) {
        return <ErrorBanner variant="inline" message={t("sessions.load_error")} onRetry={() => void load()} />;
    }
    if (items === null) {
        return <p aria-busy="true" className="text-sm text-[var(--ukip-muted)]">{t("sessions.loading")}</p>;
    }

    const others = items.filter(item => !item.current);
    const bulkTargets = scope === "self" ? others : items;

    return (
        <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm text-[var(--ukip-muted)]">{t("sessions.count", { count: items.length })}</p>
                {confirming !== "all" && (
                    <Button
                        variant="outline"
                        disabled={bulkTargets.length === 0 || busy !== null}
                        onClick={() => setConfirming("all")}
                    >
                        {scope === "self" ? t("sessions.revoke_others") : t("sessions.revoke_all")}
                    </Button>
                )}
            </div>

            {confirming === "all" && (
                <ConfirmBar
                    message={scope === "self"
                        ? t("sessions.revoke_others_confirm")
                        : t("sessions.revoke_all_confirm", { username: username ?? "" })}
                    confirmLabel={scope === "self" ? t("sessions.revoke_others") : t("sessions.revoke_all")}
                    cancelLabel={t("common.cancel")}
                    busy={busy === "all"}
                    onConfirm={() => void revoke("all")}
                    onCancel={() => setConfirming(null)}
                />
            )}

            {items.length === 0 ? (
                <p className="text-sm text-[var(--ukip-muted)]">{t("sessions.empty")}</p>
            ) : (
                <ul className="space-y-2">
                    {items.map(item => {
                        const { browser, os } = describeUserAgent(item.user_agent);
                        const device = browser && os
                            ? t("sessions.device", { browser, os })
                            : browser ?? os ?? t("sessions.unknown_device");
                        return (
                            <li
                                key={item.id}
                                className="rounded-[var(--ukip-radius-md)] border border-[var(--ukip-border)] bg-[var(--ukip-panel)] p-4"
                            >
                                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                                    <div className="min-w-0 space-y-1">
                                        <div className="flex flex-wrap items-center gap-2">
                                            <span className="font-medium text-[var(--ukip-text-strong)]" title={item.user_agent ?? undefined}>
                                                {device}
                                            </span>
                                            {item.current && <Badge variant="success" dot>{t("sessions.this_device")}</Badge>}
                                        </div>
                                        <p className="text-xs text-[var(--ukip-muted)]">
                                            {[
                                                item.ip_address ? t("sessions.ip", { ip: item.ip_address }) : null,
                                                t("sessions.last_active", { when: formatRelativeTime(item.last_seen_at, language) }),
                                                t("sessions.signed_in", { when: formatDateTime(item.created_at, language) }),
                                            ].filter(Boolean).join(" · ")}
                                        </p>
                                        {item.current && scope === "self" && (
                                            <p className="text-xs text-[var(--ukip-muted)]">{t("sessions.current_hint")}</p>
                                        )}
                                    </div>
                                    {!item.current && confirming !== item.id && (
                                        <Button
                                            variant="outline"
                                            className="shrink-0"
                                            disabled={busy !== null}
                                            aria-label={t("sessions.revoke_aria", { device })}
                                            onClick={() => setConfirming(item.id)}
                                        >
                                            {t("sessions.revoke")}
                                        </Button>
                                    )}
                                </div>
                                {confirming === item.id && (
                                    <ConfirmBar
                                        className="mt-3"
                                        message={t("sessions.revoke_confirm")}
                                        confirmLabel={t("sessions.revoke")}
                                        cancelLabel={t("common.cancel")}
                                        busy={busy === item.id}
                                        onConfirm={() => void revoke(item.id)}
                                        onCancel={() => setConfirming(null)}
                                    />
                                )}
                            </li>
                        );
                    })}
                </ul>
            )}
        </div>
    );
}

function ConfirmBar({
    message,
    confirmLabel,
    cancelLabel,
    busy,
    onConfirm,
    onCancel,
    className = "",
}: {
    message: string;
    confirmLabel: string;
    cancelLabel: string;
    busy: boolean;
    onConfirm: () => void;
    onCancel: () => void;
    className?: string;
}) {
    return (
        <div
            role="alertdialog"
            aria-label={message}
            className={`flex flex-col gap-3 rounded-[var(--ukip-radius-md)] border border-[var(--ukip-danger)] bg-[var(--ukip-danger-soft)] p-3 sm:flex-row sm:items-center sm:justify-between ${className}`}
        >
            <p className="text-sm text-[var(--ukip-text-strong)]">{message}</p>
            <div className="flex shrink-0 gap-2">
                <Button variant="secondary" onClick={onCancel} disabled={busy}>{cancelLabel}</Button>
                <Button variant="danger" onClick={onConfirm} loading={busy}>{confirmLabel}</Button>
            </div>
        </div>
    );
}
