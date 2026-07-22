#!/usr/bin/env node
/**
 * npm-audit gate with allowlist (EPIC-019, ER-SDLC-001).
 * Fails on HIGH/CRITICAL advisories in production deps unless allowlisted
 * (and not expired). npm audit has no native baseline, hence this wrapper.
 *
 * Note: purely transitive vulns (via entries that are all strings) yield no
 * advisory ids. They are allowed only when every package they point at is
 * itself fully allowlisted (fixpoint propagation below); otherwise they fail
 * closed. Example: `next` flagged solely via `sharp` clears once sharp's
 * advisory is allowlisted — there is no separate advisory to key an entry on.
 */
import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";

const SEVERITIES = new Set(["high", "critical"]);

const allowlistFile = new URL("../.npm-audit-allowlist.json", import.meta.url);
let allowlist;
try {
  const parsed = JSON.parse(readFileSync(allowlistFile, "utf8"));
  if (!Array.isArray(parsed.allowlist)) {
    throw new Error(`"allowlist" key must be an array, got ${typeof parsed.allowlist}`);
  }
  allowlist = parsed.allowlist;
} catch (err) {
  console.error(`[npm-audit-gate] Cannot load allowlist from ${allowlistFile.pathname}: ${err.message}`);
  console.error("This is a gate configuration error, NOT a clean audit — do not suppress this step.");
  process.exit(2);
}
const today = new Date().toISOString().slice(0, 10);

const active = new Map();
for (const entry of allowlist) {
  // Expiry semantics: the entry stays active THROUGH its expiry date
  // (enforcement starts the following day).
  if (!entry.expires || entry.expires >= today) {
    active.set(String(entry.id), entry);
  } else {
    console.warn(`[npm-audit-gate] allowlist entry EXPIRED (now enforced): ${entry.id}`);
  }
}

let raw;
try {
  raw = execSync("npm audit --omit=dev --json", { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
} catch (err) {
  // npm audit exits non-zero when vulnerabilities exist; the JSON is still on stdout.
  if (!err.stdout) {
    console.error("[npm-audit-gate] npm audit produced no output — failing loud.");
    console.error(err.message);
    process.exit(2);
  }
  raw = err.stdout;
}

let report;
try {
  report = JSON.parse(raw);
} catch (err) {
  console.error("[npm-audit-gate] Failed to parse npm audit JSON output.");
  console.error(err.message);
  console.error("Raw output (first 500 chars):", raw.slice(0, 500));
  process.exit(2);
}
// npm 7+ always emits a `vulnerabilities` key (possibly empty). Its absence
// means a schema we don't understand — fail loud rather than report clean.
if (!report.vulnerabilities || typeof report.vulnerabilities !== "object") {
  console.error("[npm-audit-gate] Unexpected audit report schema — 'vulnerabilities' key missing.");
  console.error("Report keys:", Object.keys(report).join(", "));
  process.exit(2);
}
const vulns = report.vulnerabilities;

// Pass 1 — packages whose own advisories (object vias) are all allowlisted.
// Pass 2..n — propagate through string vias to a fixpoint: a package flagged
// only *via* other packages is allowed exactly when every one of those
// packages is itself allowed. Fail-closed is preserved: propagation only ever
// flows FROM explicit allowlist entries, never around them, and a via chain
// touching any non-allowed package stays blocking.
const allowed = new Set();
let changed = true;
while (changed) {
  changed = false;
  for (const [name, vuln] of Object.entries(vulns)) {
    if (allowed.has(name) || !SEVERITIES.has(vuln.severity)) continue;
    const via = vuln.via ?? [];
    const objectIds = via
      .filter((v) => typeof v === "object")
      .map((v) => String(v.source ?? v.ghsaId ?? v.url ?? ""))
      .filter((id) => id !== "");
    const viaPackages = via.filter((v) => typeof v === "string");
    if (objectIds.length === 0 && viaPackages.length === 0) continue; // nothing to key on — stays blocking
    const idsOk = objectIds.every((id) => active.has(id));
    const viasOk = viaPackages.every((pkg) => allowed.has(pkg));
    if (idsOk && viasOk) {
      allowed.add(name);
      changed = true;
    }
  }
}

const blocking = [];
for (const [name, vuln] of Object.entries(vulns)) {
  if (!SEVERITIES.has(vuln.severity) || allowed.has(name)) continue;
  const ids = (vuln.via ?? [])
    .filter((v) => typeof v === "object")
    .map((v) => String(v.source ?? v.ghsaId ?? v.url ?? ""))
    .filter((id) => id !== "");
  blocking.push({ name, severity: vuln.severity, ids, via: vuln.via });
}

if (blocking.length > 0) {
  console.error(`[npm-audit-gate] BLOCKING: ${blocking.length} non-allowlisted high/critical advisories:`);
  for (const b of blocking) {
    console.error(`  - ${b.name} (${b.severity}) advisories: ${b.ids.join(", ") || "n/a"}`);
    if (b.ids.length === 0) {
      // No extractable id — show the raw via so the engineer can key an allowlist entry.
      console.error(`    raw via: ${JSON.stringify(b.via)}`);
    }
  }
  console.error("Fix the dependency or add a documented allowlist entry (see docs/operating/SECURITY_GATES.md).");
  process.exit(1);
}

console.log("[npm-audit-gate] OK — no non-allowlisted high/critical production advisories.");
