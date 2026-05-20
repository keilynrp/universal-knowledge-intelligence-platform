"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "./AuthContext";

const DOMAIN_STORAGE_KEY = "ukip_active_domain";
const ALL_DOMAINS_ID = "all";

// ---------------------------------------------------------------------------
// DomainScope contract
// ---------------------------------------------------------------------------

/**
 * Canonical domain scope type.  Legal values:
 * - `"all"`              — aggregate over all records regardless of domain
 * - `"domain:{id}"`      — records where domain == id (exact match)
 * - `"legacy_default"`   — records where domain == "default" OR domain IS NULL
 *
 * Use the helper functions below instead of raw string comparisons.
 */
export type DomainScope = string;

/** Returns true when the scope represents the aggregate-all view. */
export function isAllScope(scope: DomainScope): boolean {
    return scope === "all";
}

/** Returns true when the scope targets legacy/default-domain records. */
export function isLegacyScope(scope: DomainScope): boolean {
    return scope === "legacy_default";
}

/**
 * Extracts the concrete domain ID from a DomainScope.
 *
 * - `"domain:science"` → `"science"`
 * - `"all"`            → `null`
 * - `"legacy_default"` → `null`
 * - `"science"` (bare) → `"science"` (backward-compatible for current context values)
 */
export function domainIdFromScope(scope: DomainScope): string | null {
    if (isAllScope(scope) || isLegacyScope(scope)) return null;
    if (scope.startsWith("domain:")) return scope.slice("domain:".length);
    // Bare domain ID — current context format; return as-is
    return scope || null;
}

export interface DomainAttribute {
    name: string;
    type: string;
    label: string;
    required: boolean;
    is_core: boolean;
}

export interface ParadigmIndicators {
    terms: string[];
    document_types: string[];
    journals_affinity: string[];
}

export interface Paradigm {
    id: string;
    label: string;
    description: string;
    indicators: ParadigmIndicators;
}

export interface EpistemologyConfig {
    paradigms: Paradigm[];
    evidence_hierarchy: { level: number; label: string; weight: number }[];
}

export interface DomainSchema {
    id: string;
    name: string;
    description: string;
    primary_entity: string;
    icon: string;
    attributes: DomainAttribute[];
    entity_count?: number | null;
    first_entity_id?: number | null;
    epistemology?: EpistemologyConfig | null;
}

interface DomainContextType {
    domains: DomainSchema[];
    activeDomainId: DomainScope;
    activeDomain: DomainSchema | null;
    setActiveDomainId: (scope: DomainScope) => void;
    isLoading: boolean;
    refreshDomains: () => Promise<void>;
}

const DomainContext = createContext<DomainContextType | undefined>(undefined);

function readStoredDomain(): string | null {
    if (typeof window === "undefined") return null;
    const stored = window.localStorage.getItem(DOMAIN_STORAGE_KEY);
    return stored === "default" ? ALL_DOMAINS_ID : stored;
}

export function DomainProvider({ children }: { children: React.ReactNode }) {
    const { token, isAuthenticated } = useAuth();
    const [domains, setDomains] = useState<DomainSchema[]>([]);
    const [activeDomainId, setActiveDomainId] = useState<string>(() => readStoredDomain() || ALL_DOMAINS_ID);
    const [isLoading, setIsLoading] = useState(true);

    const firstIngestedDomain = useCallback((availableDomains: DomainSchema[]) => {
        return [...availableDomains]
            .filter((domain) => (domain.entity_count ?? 0) > 0)
            .sort((a, b) => (a.first_entity_id ?? Number.MAX_SAFE_INTEGER) - (b.first_entity_id ?? Number.MAX_SAFE_INTEGER))[0];
    }, []);

    const resolveDomainSelection = useCallback((availableDomains: DomainSchema[], currentActiveDomainId: string, preferStored: boolean) => {
        if (availableDomains.length === 0) {
            return ALL_DOMAINS_ID;
        }

        const firstIngested = firstIngestedDomain(availableDomains);
        const savedDomain = readStoredDomain();

        if (!firstIngested) {
            return ALL_DOMAINS_ID;
        }

        if (preferStored && currentActiveDomainId && currentActiveDomainId !== ALL_DOMAINS_ID && availableDomains.some((d) => d.id === currentActiveDomainId)) {
            return currentActiveDomainId;
        }

        if (preferStored && savedDomain && savedDomain !== ALL_DOMAINS_ID && availableDomains.some((d) => d.id === savedDomain)) {
            return savedDomain;
        }

        return firstIngested.id;
    }, [firstIngestedDomain]);

    const fetchDomains = useCallback(async ({ preferStored = true }: { preferStored?: boolean } = {}) => {
        if (!isAuthenticated || !token) {
            setDomains([]);
            setActiveDomainId(ALL_DOMAINS_ID);
            setIsLoading(false);
            return;
        }
        setIsLoading(true);
        try {
            const res = await apiFetch("/domains");
            if (res.ok) {
                const data: DomainSchema[] = await res.json();
                const ordered = [...data].sort((a, b) => {
                    const aHasData = (a.entity_count ?? 0) > 0;
                    const bHasData = (b.entity_count ?? 0) > 0;
                    if (aHasData !== bHasData) return aHasData ? -1 : 1;
                    return (a.first_entity_id ?? Number.MAX_SAFE_INTEGER) - (b.first_entity_id ?? Number.MAX_SAFE_INTEGER);
                });
                setDomains(ordered);

                setActiveDomainId((prev) => {
                    const next = resolveDomainSelection(ordered, prev, preferStored);
                    if (typeof window !== "undefined") {
                        window.localStorage.setItem(DOMAIN_STORAGE_KEY, next);
                    }
                    return next;
                });
            }
        } catch {
            setDomains([]);
            setActiveDomainId(ALL_DOMAINS_ID);
        } finally {
            setIsLoading(false);
        }
    }, [isAuthenticated, resolveDomainSelection, token]);

    useEffect(() => {
        const storedDomain = readStoredDomain();
        if (storedDomain) {
            setActiveDomainId((prev) => prev || storedDomain);
        }
    }, []);

    useEffect(() => {
        void fetchDomains({ preferStored: false });
    }, [fetchDomains, token]);

    const handleSetActiveDomain = (id: string) => {
        if (!id) return;
        setActiveDomainId(id);
        if (typeof window !== "undefined") {
            window.localStorage.setItem(DOMAIN_STORAGE_KEY, id);
        }
    };

    const activeDomain =
        activeDomainId === ALL_DOMAINS_ID
            ? null
            : domains.find((d) => d.id === activeDomainId)
              || domains.find((d) => d.id === "default")
              || domains[0]
              || null;
    const resolvedActiveDomainId = activeDomainId === ALL_DOMAINS_ID
        ? ALL_DOMAINS_ID
        : activeDomain?.id || activeDomainId || ALL_DOMAINS_ID;

    return (
        <DomainContext.Provider value={{
            domains,
            activeDomainId: resolvedActiveDomainId,
            activeDomain,
            setActiveDomainId: handleSetActiveDomain,
            isLoading,
            refreshDomains: fetchDomains,
        }}>
            {children}
        </DomainContext.Provider>
    );
}

export function useDomain() {
    const context = useContext(DomainContext);
    if (!context) {
        throw new Error("useDomain must be used within a DomainProvider");
    }
    return context;
}
