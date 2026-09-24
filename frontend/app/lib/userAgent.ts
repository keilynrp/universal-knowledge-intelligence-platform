/**
 * A readable name for the device behind a session, from its User-Agent.
 *
 * Deliberately coarse: browser family and operating system are enough for a
 * person to tell "my laptop" from "not mine", which is the decision the
 * sessions list exists for. Versions are left out because they change on every
 * update and would make one device look like several.
 */
export type DeviceDescription = { browser: string | null; os: string | null };

// Order matters: Edge and Opera also announce Chrome, and Chrome announces Safari.
const BROWSERS: [RegExp, string][] = [
    [/\bEdg(?:e|A|iOS)?\//, "Edge"],
    [/\bOPR\/|\bOpera\b/, "Opera"],
    [/\bFirefox\/|\bFxiOS\//, "Firefox"],
    [/\bSamsungBrowser\//, "Samsung Internet"],
    [/\bChrome\/|\bCriOS\//, "Chrome"],
    [/\bSafari\//, "Safari"],
    [/\bcurl\//i, "curl"],
    [/\bpython-requests\/|\bpython-httpx\/|\bhttpx\//i, "Python"],
];

// iPadOS and iOS before Android/macOS: their agents mention "like Mac OS X".
const SYSTEMS: [RegExp, string][] = [
    [/\biPhone\b|\biPad\b|\biPod\b/, "iOS"],
    [/\bAndroid\b/, "Android"],
    [/\bWindows\b/, "Windows"],
    [/\bMac OS X\b|\bMacintosh\b/, "macOS"],
    [/\bCrOS\b/, "ChromeOS"],
    [/\bLinux\b/, "Linux"],
];

function firstMatch(ua: string, table: [RegExp, string][]): string | null {
    for (const [pattern, name] of table) {
        if (pattern.test(ua)) return name;
    }
    return null;
}

export function describeUserAgent(ua: string | null | undefined): DeviceDescription {
    if (!ua) return { browser: null, os: null };
    return { browser: firstMatch(ua, BROWSERS), os: firstMatch(ua, SYSTEMS) };
}
