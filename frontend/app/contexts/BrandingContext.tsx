"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";

export interface BrandingSettings {
  platform_name: string;
  logo_url: string;
  accent_color: string;
  footer_text: string;
}

const DEFAULTS: BrandingSettings = {
  platform_name: "UKIP",
  logo_url: "",
  accent_color: "#6366f1",
  footer_text: "Universal Knowledge Intelligence Platform",
};

interface BrandingContextType {
  branding: BrandingSettings;
  refreshBranding: () => Promise<void>;
}

const BrandingContext = createContext<BrandingContextType | undefined>(undefined);

export function BrandingProvider({ children }: { children: React.ReactNode }) {
  const [branding, setBranding] = useState<BrandingSettings>(DEFAULTS);

  const refreshBranding = useCallback(async () => {
    try {
      // Use raw fetch — this is a public endpoint, no auth needed at app load
      const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const res = await fetch(`${apiUrl}/branding/settings`);
      if (res.ok) {
        const data = await res.json();
        setBranding({ ...DEFAULTS, ...data });
      }
    } catch {
      // Non-critical — keep defaults on failure
    }
  }, []);

  useEffect(() => {
    refreshBranding();
  }, [refreshBranding]);

  return (
    <BrandingContext.Provider value={{ branding, refreshBranding }}>
      {children}
    </BrandingContext.Provider>
  );
}

export function useBranding(): BrandingContextType {
  const ctx = useContext(BrandingContext);
  if (!ctx) throw new Error("useBranding must be used within a BrandingProvider");
  return ctx;
}
