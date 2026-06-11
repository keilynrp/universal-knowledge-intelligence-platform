#!/usr/bin/env node
/**
 * npm-audit gate with allowlist (EPIC-019, ER-SDLC-001).
 * Fails on HIGH/CRITICAL advisories in production deps unless allowlisted
 * (and not expired). npm audit has no native baseline, hence this wrapper.
 *
 * Note: purely transitive vulns (via entries that are all strings) yield no
 * advisory ids; those fail closed and must be allowlisted at the direct-dep
 * level if ever needed.
 */
import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";

const SEVERITIES = new Set(["high", "critical"]);

const allowlistFile = new URL("../.npm-audit-allowlist.json", import.meta.url);
const { allowlist } = JSON.parse(readFileSync(allowlistFile, "utf8"));
const today = new Date().toISOString().slice(0, 10);

const active = new Map();
for (const entry of allowlist) {
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

const report = JSON.parse(raw);
const vulns = report.vulnerabilities ?? {};
const blocking = [];

for (const [name, vuln] of Object.entries(vulns)) {
  if (!SEVERITIES.has(vuln.severity)) continue;
  // Advisory ids live in vuln.via entries that are objects (not strings).
  const ids = (vuln.via ?? [])
    .filter((v) => typeof v === "object")
    .map((v) => String(v.source ?? v.url?.split("/").pop() ?? ""));
  const allAllowed = ids.length > 0 && ids.every((id) => active.has(id));
  if (!allAllowed) {
    blocking.push({ name, severity: vuln.severity, ids });
  }
}

if (blocking.length > 0) {
  console.error(`[npm-audit-gate] BLOCKING: ${blocking.length} non-allowlisted high/critical advisories:`);
  for (const b of blocking) {
    console.error(`  - ${b.name} (${b.severity}) advisories: ${b.ids.join(", ") || "n/a"}`);
  }
  console.error("Fix the dependency or add a documented allowlist entry (see docs/operating/SECURITY_GATES.md).");
  process.exit(1);
}

console.log("[npm-audit-gate] OK — no non-allowlisted high/critical production advisories.");
