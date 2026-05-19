"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "./AuthContext";

const DOMAIN_STORAGE_KEY = "ukip_active_domain";
const ALL_DOMAINS_ID = "all";

export interface DomainAttribute {
    name: string;
    type: string;
    label: string;
    required: boolean;
    is_core: boolean;
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
}

interface DomainContextType {
    domains: DomainSchema[];
    activeDomainId: string;
    activeDomain: DomainSchema | null;
    setActiveDomainId: (id: string) => void;
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
