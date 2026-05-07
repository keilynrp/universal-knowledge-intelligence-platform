"use client";

import { useEffect } from "react";
import { useBranding } from "../contexts/BrandingContext";
import { DEFAULT_FAVICON_PATH } from "../lib/brandingAssets";

/**
 * Reads favicon_url from BrandingContext and dynamically updates
 * <link rel="icon"> in the browser <head>.
 * When no custom favicon is set, the default UKIP favicon asset is used.
 */
export default function FaviconInjector() {
  const { branding } = useBranding();
  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  useEffect(() => {
    const faviconUrl = branding.favicon_url
      ? branding.favicon_url.startsWith("/static/")
        ? `${apiBase}${branding.favicon_url}`
        : branding.favicon_url
      : DEFAULT_FAVICON_PATH;

    // Remove existing favicon links
    document.querySelectorAll("link[rel~='icon']").forEach((el) => el.remove());

    const link = document.createElement("link");
    link.rel = "icon";
    link.href = faviconUrl;
    // Hint the browser about the type for SVG/PNG favicons
    if (faviconUrl.endsWith(".svg")) link.type = "image/svg+xml";
    else if (faviconUrl.endsWith(".png")) link.type = "image/png";
    else link.type = "image/x-icon";

    document.head.appendChild(link);
  }, [branding.favicon_url, apiBase]);

  return null;
}
