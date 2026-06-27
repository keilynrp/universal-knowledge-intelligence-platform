"use client";

import type { DomainSchema } from "../contexts/DomainContext";

export interface Entity {
    id: number;
    import_batch_id?: number | null;
    primary_label: string | null;
    secondary_label: string | null;
    canonical_id: string | null;
    entity_type: string | null;
    domain: string | null;
    validation_status: string | null;
    enrichment_status: string | null;
    enrichment_failure_reason: string | null;
    enrichment_citation_count: number | null;
    source: string | null;
    attributes_json: string | null;
    normalized_json: string | null;
    quality_score: number | null;
    enrichment_work_type?: string | null;
}

export type EditableFields = Pick<
    Entity,
    "primary_label" | "secondary_label" | "canonical_id" | "entity_type" | "domain" | "validation_status"
>;

export type EntityTableDomain = DomainSchema | null;
