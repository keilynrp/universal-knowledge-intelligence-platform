"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";

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

export function DomainProvider({ children }: { children: React.ReactNode }) {
    const [domains, setDomains] = useState<DomainSchema[]>([]);
    const [activeDomainId, setActiveDomainId] = useState<string>("default");
    const [isLoading, setIsLoading] = useState(true);

    const fetchDomains = async () => {
        try {
            const res = await apiFetch("/domains");
            if (res.ok) {
                const data = await res.json();
                setDomains(data);

                // Retrieve saved domain from localStorage, or use 'default', or first available
                const savedDomain = localStorage.getItem("ukip_active_domain");
                if (savedDomain && data.some((d: DomainSchema) => d.id === savedDomain)) {
                    setActiveDomainId(savedDomain);
                } else if (data.length > 0) {
                    const defaultDomain = data.find((d: DomainSchema) => d.id === "default");
                    setActiveDomainId(defaultDomain ? defaultDomain.id : data[0].id);
                }
            }
        } catch (error) {
            console.error("Failed to load domains", error);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => { fetchDomains(); }, []);

    const handleSetActiveDomain = (id: string) => {
        setActiveDomainId(id);
        localStorage.setItem("ukip_active_domain", id);
    };

    const activeDomain = domains.find(d => d.id === activeDomainId) || null;

    return (
        <DomainContext.Provider value={{
            domains,
            activeDomainId,
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
