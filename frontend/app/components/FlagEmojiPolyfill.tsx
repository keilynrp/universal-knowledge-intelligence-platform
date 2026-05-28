"use client";

import { useEffect } from "react";

/**
 * Loads the "Twemoji Country Flags" webfont so flag emoji render on Windows
 * (which deliberately omits regional-indicator flag glyphs from its native
 * emoji fonts). The polyfill is a no-op on platforms that already render
 * flags correctly (macOS, iOS, Android, Linux). Adds ~13 KB gz + ~77 KB
 * of webfont, loaded lazily only when needed.
 */
export default function FlagEmojiPolyfill() {
  useEffect(() => {
    let cancelled = false;
    void import("country-flag-emoji-polyfill").then(
      ({ polyfillCountryFlagEmojis }) => {
        if (!cancelled) polyfillCountryFlagEmojis();
      },
    );
    return () => {
      cancelled = true;
    };
  }, []);
  return null;
}
