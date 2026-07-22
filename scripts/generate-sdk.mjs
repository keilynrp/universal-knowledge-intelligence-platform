#!/usr/bin/env node
/**
 * Regenerate the UKIP SDK clients from the application's OpenAPI document.
 *
 *   node scripts/generate-sdk.mjs           # regenerate everything
 *   node scripts/generate-sdk.mjs --check   # fail if regeneration would change anything
 *
 * The spec is read straight off the FastAPI app object — no server, no port,
 * no database, no lifespan. That keeps the CI drift gate cheap and independent
 * of a healthy runtime (CI deliberately skips real startup).
 *
 * Generator versions are pinned in frontend/package.json. An unpinned generator
 * would produce phantom diffs on unrelated PRs, and a gate that cries wolf is a
 * gate the team learns to ignore.
 */
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const SDK_DIR = join(ROOT, "sdk");
const SPEC_PATH = join(SDK_DIR, "openapi.json");

const CHECK_ONLY = process.argv.includes("--check");

/** Windows keeps its venv executables in Scripts/, POSIX in bin/. */
function pythonExecutable() {
  const candidates = [
    join(ROOT, ".venv", "Scripts", "python.exe"),
    join(ROOT, ".venv", "bin", "python"),
  ];
  return candidates.find((candidate) => existsSync(candidate)) ?? "python";
}

function dumpSpec() {
  const code = [
    "import json, sys",
    "from backend.main import app",
    // sort_keys so the committed file is diffable rather than dict-order noise
    "sys.stdout.write(json.dumps(app.openapi(), indent=2, sort_keys=True))",
  ].join("; ");

  return execFileSync(pythonExecutable(), ["-c", code], {
    cwd: ROOT,
    encoding: "utf8",
    maxBuffer: 128 * 1024 * 1024,
    // The app logs warnings to stderr on import (missing dev secrets); those
    // are not our problem here and must not pollute the captured stdout.
    stdio: ["ignore", "pipe", "ignore"],
  });
}

/** CRLF -> LF, so the check measures content rather than checkout settings. */
function normalizeEol(text) {
  return text.replace(/\r\n/g, "\n");
}

function main() {
  mkdirSync(SDK_DIR, { recursive: true });

  const spec = dumpSpec().trimEnd() + "\n";

  if (CHECK_ONLY) {
    const committed = existsSync(SPEC_PATH) ? readFileSync(SPEC_PATH, "utf8") : "";
    // Compare content, not line endings. .gitattributes pins this file to LF,
    // but a checkout predating that rule (or a differently configured client)
    // still has CRLF on disk — and a gate that reports drift no regeneration
    // can fix is a gate people learn to bypass.
    if (normalizeEol(committed) !== normalizeEol(spec)) {
      console.error(
        "[generate-sdk] DRIFT: sdk/openapi.json is stale.\n" +
          "The API surface changed without regenerating the SDK.\n" +
          "Run:  node scripts/generate-sdk.mjs",
      );
      process.exit(1);
    }
    console.log("[generate-sdk] OK — sdk/openapi.json matches the application.");
    return;
  }

  writeFileSync(SPEC_PATH, spec, "utf8");
  const operations = Object.values(JSON.parse(spec).paths).reduce(
    (total, methods) => total + Object.keys(methods).length,
    0,
  );
  console.log(`[generate-sdk] wrote sdk/openapi.json (${operations} operations)`);
}

main();
