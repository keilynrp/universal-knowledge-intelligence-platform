"use client";

export interface VariationGroup {
    main: string;
    variations: string[];
    count: number;
    has_rules?: boolean;
    resolved_to?: string | null;
    algorithm_used?: string;
}

export interface DisambiguationResponse {
    groups: VariationGroup[];
    total_groups: number;
    algorithm?: string;
}

export interface AuthorityRecord {
    id: number;
    authority_source: string;
    authority_id: string;
    canonical_label: string;
    aliases: string[];
    description: string | null;
    confidence: number;
    uri: string | null;
    status: string;
    score_breakdown?: Record<string, number> | null;
    evidence?: string[] | null;
    resolution_status?: string | null;
}

export const SOURCE_STYLES: Record<string, { label: string; bg: string; text: string }> = {
    wikidata: { label: "Wikidata", bg: "bg-amber-100 dark:bg-amber-500/20", text: "text-amber-800 dark:text-amber-300" },
    viaf: { label: "VIAF", bg: "bg-blue-100 dark:bg-blue-500/20", text: "text-blue-800 dark:text-blue-300" },
    orcid: { label: "ORCID", bg: "bg-green-100 dark:bg-green-500/20", text: "text-green-800 dark:text-green-300" },
    dbpedia: { label: "DBpedia", bg: "bg-red-100 dark:bg-red-500/20", text: "text-red-800 dark:text-red-300" },
    openalex: { label: "OpenAlex", bg: "bg-violet-100 dark:bg-violet-500/20", text: "text-violet-800 dark:text-violet-300" },
};

export const ALGORITHMS = [
    {
        value: "token_sort",
        label: "Token Sort",
        tip: "Agrupa variantes por orden de palabras: 'Smith John' ~= 'John Smith'. Ideal para nombres de personas y marcas.",
    },
    {
        value: "fingerprint",
        label: "Fingerprint",
        tip: "Normaliza puntuacion y mayusculas antes de comparar: 'Apple, Inc.' ~= 'inc apple'. Ideal para datos inconsistentes.",
    },
    {
        value: "ngram",
        label: "N-gram",
        tip: "Similitud por bigramas de caracteres (Jaccard). Robusto ante errores tipograficos y OCR: 'colour' ~= 'color'.",
    },
    {
        value: "phonetic",
        label: "Fonetico",
        tip: "Agrupa por sonido (Cologne + Metaphone): 'Muller' ~= 'Mueller'. Ideal para nombres europeos con grafias distintas.",
    },
];

export const ENTITY_TYPES = [
    { value: "general", label: "General" },
    { value: "organization", label: "Organization / Brand" },
    { value: "person", label: "Person / Author" },
    { value: "institution", label: "Institution" },
    { value: "concept", label: "Concept / Category" },
];
