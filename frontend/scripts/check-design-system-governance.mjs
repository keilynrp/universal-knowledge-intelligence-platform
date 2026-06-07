import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, "..");
const appRoot = path.join(frontendRoot, "app");
const baselinePath = path.join(scriptDir, "design-system-baseline.json");
const reportOnly = process.argv.includes("--report");

const rules = {
  rawButtons: /<button\b/g,
  rawInputs: /<input\b/g,
  rawSelects: /<select\b/g,
  rawTextareas: /<textarea\b/g,
  directPaletteClasses:
    /\b(?:bg|text|border|ring|outline|fill|stroke|from|via|to)-(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)(?:-|\/)/g,
  transitionAll: /\btransition-all\b/g,
  hardcodedColors: /#[0-9a-fA-F]{3,8}\b|rgba?\(/g,
};

function walk(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const absolutePath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      return walk(absolutePath);
    }
    return /\.(?:ts|tsx|css)$/.test(entry.name) ? [absolutePath] : [];
  });
}

function isGovernedPrimitive(file) {
  return file.includes(`${path.sep}components${path.sep}ui${path.sep}`);
}

function countMatches(source, pattern) {
  return source.match(pattern)?.length ?? 0;
}

const files = walk(appRoot).filter((file) => !isGovernedPrimitive(file));
const counts = Object.fromEntries(Object.keys(rules).map((rule) => [rule, 0]));

for (const file of files) {
  const source = fs.readFileSync(file, "utf8");
  for (const [rule, pattern] of Object.entries(rules)) {
    counts[rule] += countMatches(source, pattern);
  }
}

if (reportOnly) {
  process.stdout.write(`${JSON.stringify(counts, null, 2)}\n`);
  process.exit(0);
}

if (!fs.existsSync(baselinePath)) {
  console.error(`Design System baseline is missing: ${baselinePath}`);
  process.exit(1);
}

const baseline = JSON.parse(fs.readFileSync(baselinePath, "utf8"));
const regressions = Object.entries(counts).filter(([rule, count]) => count > baseline[rule]);

if (regressions.length > 0) {
  console.error("Design System governance regression detected:");
  for (const [rule, count] of regressions) {
    console.error(`- ${rule}: ${count} exceeds baseline ${baseline[rule]}`);
  }
  console.error("Use governed primitives/tokens or reduce an existing violation in the same PR.");
  process.exit(1);
}

console.log("Design System governance baseline passed.");
for (const [rule, count] of Object.entries(counts)) {
  const delta = baseline[rule] - count;
  console.log(`- ${rule}: ${count}/${baseline[rule]}${delta > 0 ? ` (${delta} reduced)` : ""}`);
}
