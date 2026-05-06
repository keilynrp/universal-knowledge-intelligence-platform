/* eslint-disable @next/next/no-img-element */
"use client";

import { useEffect, useState, type CSSProperties } from "react";
import type { BrandingSettings } from "@/app/contexts/BrandingContext";

type BrandLockupSize = "sm" | "md" | "lg";

type BrandLockupProps = {
  branding: BrandingSettings;
  showText?: boolean;
  size?: BrandLockupSize;
  className?: string;
  markClassName?: string;
  textClassName?: string;
};

const sizeClasses: Record<BrandLockupSize, { mark: string; title: string; subtitle: string; gap: string }> = {
  sm: {
    mark: "h-8 w-8 rounded-xl",
    title: "text-sm",
    subtitle: "text-[10px]",
    gap: "gap-2",
  },
  md: {
    mark: "h-10 w-10 rounded-2xl",
    title: "text-base",
    subtitle: "text-xs",
    gap: "gap-2.5",
  },
  lg: {
    mark: "h-12 w-12 rounded-2xl",
    title: "text-lg",
    subtitle: "text-sm",
    gap: "gap-3",
  },
};

function resolveLogoUrl(logoUrl: string) {
  if (!logoUrl) return "";
  const apiBase = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
  return logoUrl.startsWith("/static/") ? `${apiBase}${logoUrl}` : logoUrl;
}

function UKIPMarkSvg() {
  return (
    <svg className="h-[62%] w-[62%] text-white" viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <circle cx="16" cy="9.5" r="3.25" stroke="currentColor" strokeWidth="2.1" />
      <circle cx="10" cy="20.5" r="3.25" stroke="currentColor" strokeWidth="2.1" />
      <circle cx="22" cy="20.5" r="3.25" stroke="currentColor" strokeWidth="2.1" />
      <path
        d="M14.38 12.32 11.62 17.7M17.62 12.32l2.76 5.38M13.45 20.5h5.1"
        stroke="currentColor"
        strokeWidth="2.1"
        strokeLinecap="round"
      />
      <path
        d="M16 3.75c5.6 0 10.25 4.18 10.25 9.32 0 5.92-5.1 9.65-10.25 15.18C10.85 22.72 5.75 18.99 5.75 13.07 5.75 7.93 10.4 3.75 16 3.75Z"
        stroke="currentColor"
        strokeWidth="1.35"
        strokeLinejoin="round"
        opacity="0.76"
      />
    </svg>
  );
}

export default function BrandLockup({
  branding,
  showText = true,
  size = "md",
  className = "",
  markClassName = "",
  textClassName = "",
}: BrandLockupProps) {
  const logoSrc = resolveLogoUrl(branding.logo_url);
  const [logoFailed, setLogoFailed] = useState(false);
  const classes = sizeClasses[size];
  const platformName = branding.platform_name?.trim() || "UKIP";
  const subtitle = branding.footer_text?.trim();
  const markStyle = {
    "--ukip-brand-accent": branding.accent_color || "var(--ukip-primary)",
  } as CSSProperties;

  useEffect(() => {
    setLogoFailed(false);
  }, [logoSrc]);

  return (
    <div className={`flex min-w-0 items-center ${classes.gap} ${className}`}>
      <span
        className={`flex shrink-0 items-center justify-center overflow-hidden ${classes.mark} bg-[var(--ukip-brand-accent)] shadow-[0_10px_24px_rgb(124_58_237_/_0.22)] ${markClassName}`}
        style={markStyle}
      >
        {logoSrc && !logoFailed ? (
          <img
            src={logoSrc}
            alt=""
            className="h-full w-full object-contain p-1.5"
            onError={(event) => {
              event.currentTarget.hidden = true;
              setLogoFailed(true);
            }}
          />
        ) : (
          <UKIPMarkSvg />
        )}
      </span>

      {showText && (
        <span className={`min-w-0 leading-none ${textClassName}`}>
          <span className={`block truncate font-black tracking-[-0.04em] text-slate-950 dark:text-[var(--ukip-text-strong)] ${classes.title}`}>
            {platformName}
          </span>
          {subtitle && (
            <span className={`mt-1 block truncate font-semibold leading-none text-slate-500 dark:text-[var(--ukip-muted)] ${classes.subtitle}`}>
              {subtitle}
            </span>
          )}
        </span>
      )}
    </div>
  );
}
