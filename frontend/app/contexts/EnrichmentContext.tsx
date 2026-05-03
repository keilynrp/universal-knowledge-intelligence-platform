"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { apiFetch } from "@/lib/api";
import type { EnrichStats } from "../analytics/analyticsTypes";

interface EnrichmentContextValue {
  enrichStats: EnrichStats | null;
  enrichPct: number;
  isPolling: boolean;
  startPolling: () => void;
  refreshStats: () => Promise<void>;
}

const EnrichmentContext = createContext<EnrichmentContextValue>({
  enrichStats: null,
  enrichPct: 0,
  isPolling: false,
  startPolling: () => {},
  refreshStats: async () => {},
});

export function EnrichmentProvider({ children }: { children: React.ReactNode }) {
  const [enrichStats, setEnrichStats] = useState<EnrichStats | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchStats = useCallback(async () => {
    try {
      const res = await apiFetch("/enrich/stats");
      if (!res.ok) return;
      const data: EnrichStats = await res.json();
      setEnrichStats(data);
      // Auto-stop when no more pending work
      if (data.pending_count === 0 && pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
        setIsPolling(false);
      }
    } catch {
      // Non-critical — leave existing stats in place
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchStats();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [fetchStats]);

  const startPolling = useCallback(() => {
    if (pollRef.current) return; // Already running
    setIsPolling(true);
    pollRef.current = setInterval(fetchStats, 5000);
  }, [fetchStats]);

  return (
    <EnrichmentContext.Provider
      value={{
        enrichStats,
        enrichPct: enrichStats?.enrichment_coverage_pct ?? 0,
        isPolling,
        startPolling,
        refreshStats: fetchStats,
      }}
    >
      {children}
    </EnrichmentContext.Provider>
  );
}

export function useEnrichment() {
  return useContext(EnrichmentContext);
}
