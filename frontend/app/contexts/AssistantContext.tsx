"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";
import { useDomain } from "./DomainContext";

export type AssistantContext = {
  route: string;
  domainId: string;
  moduleLabel?: string | null;
  totalEntities?: number | null;
  enrichedCount?: number | null;
  enrichmentPct?: number | null;
  qualityPct?: number | null;
  readinessPct?: number | null;
  activeSources?: number | null;
  leadingGap?: string | null;
  recommendedActions?: string[];
  actionLinks?: AssistantActionLink[];
};

export type AssistantActionLink = {
  id: string;
  label: string;
  href: string;
  kind?: "navigate" | "preview" | "export" | "mutation";
  requiresConfirmation?: boolean;
  confirmationLabel?: string;
};

type AssistantContextValue = {
  context: AssistantContext;
  setAssistantContext: (nextContext: Partial<AssistantContext> | null) => void;
};

const AssistantContextState = createContext<AssistantContextValue | undefined>(undefined);

function routeModuleLabel(pathname: string) {
  if (pathname.startsWith("/analytics/dashboard")) return "Dashboard ejecutivo";
  if (pathname.startsWith("/catalogs")) return "Catalogo publico";
  if (pathname.startsWith("/entities")) return "Catalogo interno";
  if (pathname.startsWith("/import")) return "Ingesta y mapeo";
  if (pathname.startsWith("/authority")) return "Control de autoridad";
  if (pathname.startsWith("/harmonization")) return "Harmonizacion";
  if (pathname.startsWith("/rag")) return "RAG semantico";
  if (pathname.startsWith("/settings")) return "Administracion";
  if (pathname.startsWith("/analytics")) return "Analitica";
  if (pathname.startsWith("/reports")) return "Reportes";
  return "Workspace UKIP";
}

export function AssistantProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { activeDomainId } = useDomain();
  const baseContext = useMemo<AssistantContext>(() => ({
    route: pathname || "/",
    domainId: activeDomainId || "all",
    moduleLabel: routeModuleLabel(pathname || "/"),
  }), [activeDomainId, pathname]);
  const [pageContext, setPageContext] = useState<Partial<AssistantContext> | null>(null);

  const setAssistantContext = useCallback((nextContext: Partial<AssistantContext> | null) => {
    setPageContext(nextContext ? { ...nextContext, route: nextContext.route ?? pathname } : null);
  }, [pathname]);

  const activePageContext = pageContext?.route === pathname ? pageContext : null;
  const context = useMemo<AssistantContext>(() => ({
    ...baseContext,
    ...(activePageContext ?? {}),
    route: activePageContext?.route ?? baseContext.route,
    domainId: activePageContext?.domainId ?? baseContext.domainId,
  }), [activePageContext, baseContext]);

  return (
    <AssistantContextState.Provider value={{ context, setAssistantContext }}>
      {children}
    </AssistantContextState.Provider>
  );
}

export function useAssistant() {
  const context = useContext(AssistantContextState);
  if (!context) throw new Error("useAssistant must be used within AssistantProvider");
  return context;
}

export function useAssistantContextRegistration(context: Partial<AssistantContext> | null) {
  const { setAssistantContext } = useAssistant();

  useEffect(() => {
    setAssistantContext(context);
    return () => setAssistantContext(null);
  }, [context, setAssistantContext]);
}
