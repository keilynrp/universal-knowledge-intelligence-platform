"use client";

import { useLanguage } from "../contexts/LanguageContext";
import { Button } from "../components/ui";
import { SOURCE_COLORS, type AuthorityRecord, type GroupedRecord } from "./reviewQueueTypes";

interface ReviewQueueGroupedTableProps {
    loadingRecords: boolean;
    groups: GroupedRecord[];
    statusFilter: string;
    rowActionId: number | null;
    onReviewRecord: (rec: AuthorityRecord, action: "confirm" | "reject") => void;
}

export default function ReviewQueueGroupedTable({
    loadingRecords,
    groups,
    statusFilter,
    rowActionId,
    onReviewRecord,
}: ReviewQueueGroupedTableProps) {
    const { t } = useLanguage();

    if (loadingRecords) {
        return <div className="px-5 py-10 text-center text-sm text-[var(--ukip-muted)]">{t("common.loading")}</div>;
    }
    if (groups.length === 0) {
        return <div className="px-5 py-10 text-center text-sm text-[var(--ukip-muted)]">{t("page.authority.no_groups")}</div>;
    }

    return (
        <div className="overflow-x-auto">
            <table className="w-full text-sm">
                <thead>
                    <tr className="border-b border-[var(--ukip-border)] text-left text-xs uppercase tracking-wide text-[var(--ukip-muted)]">
                        <th className="px-5 py-3 font-medium">{t("page.authority.grouped_by_value")}</th>
                        <th className="px-3 py-3 font-medium">{t("page.authority.best_candidate")}</th>
                        <th className="px-3 py-3 font-medium text-right">Conf.</th>
                        <th className="px-5 py-3 font-medium text-right" aria-hidden="true" />
                    </tr>
                </thead>
                <tbody>
                    {groups.map(g => {
                        const best = g.best;
                        const busy = rowActionId === best.id;
                        const sourceClass = SOURCE_COLORS[best.authority_source] ?? "bg-[var(--ukip-panel)] text-[var(--ukip-muted)]";
                        return (
                            <tr key={`${g.field_name}:${g.original_value}`} className="border-b border-[var(--ukip-border)]">
                                <td className="px-5 py-3 align-top">
                                    <div className="font-medium text-[var(--ukip-text-strong)]">{g.original_value}</div>
                                    <div className="mt-1 flex items-center gap-2 text-xs text-[var(--ukip-muted)]">
                                        <span>{g.candidate_count} {t("page.authority.candidates")}</span>
                                        {g.auto_confirmable && (
                                            <span className="rounded-full bg-violet-100 px-2 py-0.5 text-[10px] font-medium text-violet-700 dark:bg-violet-500/10 dark:text-violet-400">
                                                {t("page.authority.auto_confirmable")}
                                            </span>
                                        )}
                                    </div>
                                </td>
                                <td className="px-3 py-3 align-top">
                                    <div className="flex items-center gap-2">
                                        <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium uppercase ${sourceClass}`}>{best.authority_source}</span>
                                        <span className="text-[var(--ukip-text)]">{best.canonical_label}</span>
                                    </div>
                                    {best.uri && (
                                        <a href={best.uri} target="_blank" rel="noopener noreferrer" className="mt-0.5 block truncate text-xs text-[var(--ukip-cyan)] hover:underline">
                                            {best.uri}
                                        </a>
                                    )}
                                </td>
                                <td className="px-3 py-3 text-right align-top tabular-nums text-[var(--ukip-text)]">
                                    {g.best_confidence != null ? g.best_confidence.toFixed(2) : "—"}
                                </td>
                                <td className="px-5 py-3 text-right align-top">
                                    {statusFilter === "pending" && (
                                        <div className="inline-flex gap-1.5">
                                            <Button variant="primary" size="sm" disabled={busy} onClick={() => onReviewRecord(best, "confirm")}>
                                                {t("page.authority.confirm_button")}
                                            </Button>
                                            <Button variant="danger" size="sm" disabled={busy} onClick={() => onReviewRecord(best, "reject")}>
                                                {t("page.authority.reject_button")}
                                            </Button>
                                        </div>
                                    )}
                                </td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}
