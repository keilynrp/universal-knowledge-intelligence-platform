"use client";

export interface QueueSummary {
    total_pending: number;
    total_confirmed: number;
    total_rejected: number;
    by_field: {
        field_name: string;
        pending: number;
        confirmed: number;
        rejected: number;
        avg_confidence: number;
    }[];
}

export interface AuthorityRecord {
    id: number;
    field_name: string;
    original_value: string;
    authority_source: string;
    authority_id: string;
    canonical_label: string;
    aliases: string[];
    description: string | null;
    confidence: number;
    uri: string | null;
    status: string;
    created_at: string;
    confirmed_at: string | null;
    resolution_status: string;
    score_breakdown?: Record<string, number> | null;
    evidence?: string[] | null;
    merged_sources?: string[] | null;
    resolution_route?: string | null;
    complexity_score?: number | null;
    review_required?: boolean;
    nil_reason?: string | null;
    nil_score?: number | null;
    hierarchy_distance?: number | null;
    reformulation_applied?: boolean;
    reformulation_gain?: number | null;
    reformulation_cost_estimate?: number | null;
    reformulation_trace?: {
        enabled?: boolean;
        attempted?: boolean;
        applied?: boolean;
        provider?: string | null;
        model?: string | null;
        generated_queries?: string[];
        selected_query?: string | null;
        retrieval_gain?: number;
        candidate_count_before?: number;
        candidate_count_after?: number;
        prompt_tokens?: number;
        completion_tokens?: number;
        estimated_cost_usd?: number;
    } | null;
}

export interface AuthorQueueSummary {
    total_records: number;
    pending_review: number;
    nil_cases: number;
    by_nil_reason?: Record<string, number>;
    by_route: Record<string, number>;
    by_status: Record<string, number>;
}

export interface AuthorQueueResponse {
    total: number;
    records: AuthorityRecord[];
    summary: AuthorQueueSummary;
}

export interface AuthorMetrics {
    total_records: number;
    pending_review: number;
    nil_cases: number;
    avg_confidence: number;
    avg_complexity: number;
    avg_nil_score: number;
    review_rate: number;
    nil_rate: number;
    confirm_rate: number;
    reject_rate: number;
    reformulation_attempts: number;
    reformulation_applied: number;
    avg_reformulation_gain: number;
    reformulation_apply_rate: number;
    total_reformulation_cost: number;
    by_nil_reason: Record<string, number>;
    by_route: Record<string, number>;
    by_status: Record<string, number>;
}

export interface AuthorCompareResponse {
    subject: AuthorityRecord;
    peers: AuthorityRecord[];
    peer_count: number;
}

export interface AuthorityRecordLink {
    id: number;
    source_authority_record_id: number;
    target_authority_record_id: number;
    link_type: string;
    confidence: number;
    status: string;
    evidence: string[];
    created_at: string;
    confirmed_at: string | null;
}

export interface AuthorAffiliationLink {
    link: AuthorityRecordLink;
    institution_record: AuthorityRecord | null;
}

export interface AuthorAffiliationsResponse {
    author_record: AuthorityRecord;
    affiliations: AuthorAffiliationLink[];
}

export const SOURCE_COLORS: Record<string, string> = {
    wikidata: "bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400",
    viaf: "bg-blue-100 text-blue-700 dark:bg-blue-500/10 dark:text-blue-400",
    orcid: "bg-green-100 text-green-700 dark:bg-green-500/10 dark:text-green-400",
    dbpedia: "bg-red-100 text-red-700 dark:bg-red-500/10 dark:text-red-400",
    openalex: "bg-violet-100 text-violet-700 dark:bg-violet-500/10 dark:text-violet-400",
};
