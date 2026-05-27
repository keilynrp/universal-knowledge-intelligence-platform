// ISO alpha-2 → emoji flag (regional indicator symbols)
export function flagEmoji(code: string): string {
  if (!code || code.length !== 2 || code === "OTHER") return "🌐";
  const base = 0x1f1e6;
  const a = code.toUpperCase().charCodeAt(0) - 65;
  const b = code.toUpperCase().charCodeAt(1) - 65;
  if (a < 0 || a > 25 || b < 0 || b > 25) return "🌐";
  return String.fromCodePoint(base + a) + String.fromCodePoint(base + b);
}

// Approximate centroid lat/lon for marker placement on the stylized map
// Covers the ISO codes produced by backend/analyzers/geographic.py
export const COUNTRY_COORDS: Record<string, { lat: number; lon: number }> = {
  US: { lat: 39.8, lon: -98.5 }, CA: { lat: 56.1, lon: -106.3 }, MX: { lat: 23.6, lon: -102.5 },
  BR: { lat: -14.2, lon: -51.9 }, AR: { lat: -38.4, lon: -63.6 }, CL: { lat: -35.7, lon: -71.5 },
  CO: { lat: 4.6, lon: -74.3 }, PE: { lat: -9.2, lon: -75.0 }, VE: { lat: 6.4, lon: -66.6 },
  CU: { lat: 21.5, lon: -77.8 }, EC: { lat: -1.8, lon: -78.2 }, UY: { lat: -32.5, lon: -55.8 },
  PY: { lat: -23.4, lon: -58.4 }, BO: { lat: -16.3, lon: -63.6 }, CR: { lat: 9.7, lon: -83.8 },
  PA: { lat: 8.5, lon: -80.8 }, DO: { lat: 18.7, lon: -70.2 }, GT: { lat: 15.8, lon: -90.2 },
  HN: { lat: 15.2, lon: -86.2 }, SV: { lat: 13.8, lon: -88.9 }, NI: { lat: 12.9, lon: -85.2 },
  JM: { lat: 18.1, lon: -77.3 }, TT: { lat: 10.7, lon: -61.2 }, PR: { lat: 18.2, lon: -66.6 },
  GB: { lat: 55.4, lon: -3.4 }, FR: { lat: 46.2, lon: 2.2 }, DE: { lat: 51.2, lon: 10.5 },
  IT: { lat: 41.9, lon: 12.6 }, ES: { lat: 40.5, lon: -3.7 }, PT: { lat: 39.4, lon: -8.2 },
  NL: { lat: 52.1, lon: 5.3 }, BE: { lat: 50.5, lon: 4.5 }, CH: { lat: 46.8, lon: 8.2 },
  AT: { lat: 47.5, lon: 14.6 }, SE: { lat: 60.1, lon: 18.6 }, NO: { lat: 60.5, lon: 8.5 },
  DK: { lat: 56.3, lon: 9.5 }, FI: { lat: 61.9, lon: 25.7 }, IE: { lat: 53.4, lon: -8.2 },
  GR: { lat: 39.1, lon: 21.8 }, PL: { lat: 51.9, lon: 19.1 }, CZ: { lat: 49.8, lon: 15.5 },
  HU: { lat: 47.2, lon: 19.5 }, RO: { lat: 45.9, lon: 24.9 }, BG: { lat: 42.7, lon: 25.5 },
  HR: { lat: 45.1, lon: 15.2 }, RS: { lat: 44.0, lon: 21.0 }, SI: { lat: 46.2, lon: 14.9 },
  SK: { lat: 48.7, lon: 19.7 }, EE: { lat: 58.6, lon: 25.0 }, LV: { lat: 56.9, lon: 24.6 },
  LT: { lat: 55.2, lon: 23.9 }, LU: { lat: 49.8, lon: 6.1 }, IS: { lat: 64.9, lon: -19.0 },
  MT: { lat: 35.9, lon: 14.4 }, CY: { lat: 35.1, lon: 33.4 }, UA: { lat: 48.4, lon: 31.2 },
  RU: { lat: 61.5, lon: 105.3 }, CN: { lat: 35.9, lon: 104.2 }, JP: { lat: 36.2, lon: 138.3 },
  KR: { lat: 35.9, lon: 127.8 }, KP: { lat: 40.3, lon: 127.5 }, IN: { lat: 20.6, lon: 78.9 },
  PK: { lat: 30.4, lon: 69.3 }, BD: { lat: 23.7, lon: 90.4 }, LK: { lat: 7.9, lon: 80.8 },
  NP: { lat: 28.4, lon: 84.1 }, TW: { lat: 23.7, lon: 121.0 }, HK: { lat: 22.3, lon: 114.2 },
  SG: { lat: 1.4, lon: 103.8 }, MY: { lat: 4.2, lon: 101.9 }, TH: { lat: 15.9, lon: 100.9 },
  ID: { lat: -0.8, lon: 113.9 }, PH: { lat: 12.9, lon: 121.8 }, VN: { lat: 14.1, lon: 108.3 },
  SA: { lat: 23.9, lon: 45.1 }, AE: { lat: 23.4, lon: 53.8 }, IL: { lat: 31.0, lon: 34.9 },
  TR: { lat: 38.9, lon: 35.2 }, EG: { lat: 26.8, lon: 30.8 }, IR: { lat: 32.4, lon: 53.7 },
  IQ: { lat: 33.2, lon: 43.7 }, JO: { lat: 30.6, lon: 36.2 }, LB: { lat: 33.9, lon: 35.9 },
  QA: { lat: 25.4, lon: 51.2 }, KW: { lat: 29.3, lon: 47.5 }, OM: { lat: 21.5, lon: 55.9 },
  BH: { lat: 26.0, lon: 50.6 }, ZA: { lat: -30.6, lon: 22.9 }, NG: { lat: 9.1, lon: 8.7 },
  KE: { lat: -0.0, lon: 37.9 }, MA: { lat: 31.8, lon: -7.1 }, ET: { lat: 9.1, lon: 40.5 },
  GH: { lat: 7.9, lon: -1.0 }, TZ: { lat: -6.4, lon: 34.9 }, UG: { lat: 1.4, lon: 32.3 },
  CM: { lat: 7.4, lon: 12.4 }, SN: { lat: 14.5, lon: -14.5 }, TN: { lat: 33.9, lon: 9.5 },
  DZ: { lat: 28.0, lon: 1.7 }, LY: { lat: 26.3, lon: 17.2 }, SD: { lat: 12.9, lon: 30.2 },
  AU: { lat: -25.3, lon: 133.8 }, NZ: { lat: -40.9, lon: 174.9 },
};

// Equirectangular projection → SVG coordinates within a viewBox
export function project(lat: number, lon: number, w = 1000, h = 500) {
  const x = ((lon + 180) / 360) * w;
  const y = ((90 - lat) / 180) * h;
  return { x, y };
}
