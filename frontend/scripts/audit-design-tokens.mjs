import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const TOKEN_FILE = path.join(ROOT, "app", "styles", "tokens.css");
const UI_DIR = path.join(ROOT, "app", "components", "ui");
const TOKEN_RE = /^\s*(--ukip-[a-z0-9-]+):/gm;
const CSS_BLOCK_RE = /([^{}]+)\{([^{}]*)\}/g;
const TAILWIND_COLOR_FAMILIES =
  "slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose";
const HARDCODED_RE =
  new RegExp(
    `\\b(?:bg|text|border|ring|shadow|from|via|to|fill|stroke|outline|divide|decoration)-(?:${TAILWIND_COLOR_FAMILIES})-[0-9]+(?:\\/[0-9]+)?`,
    "g",
  );

export function auditTokenText(css) {
  const declarations = [...css.matchAll(TOKEN_RE)].map((match) => match[1]);
  const duplicateTokens = new Set();

  for (const match of css.matchAll(CSS_BLOCK_RE)) {
    const scopeTokens = [...match[2].matchAll(TOKEN_RE)].map((tokenMatch) => tokenMatch[1]);
    const scopeCounts = new Map();
    for (const token of scopeTokens) scopeCounts.set(token, (scopeCounts.get(token) ?? 0) + 1);
    for (const [token, count] of scopeCounts) {
      if (count > 1) duplicateTokens.add(token);
    }
  }

  return {
    declarations: [...new Set(declarations)].sort(),
    duplicates: [...duplicateTokens].sort(),
  };
}

export function findHardcodedColorClasses(source) {
  return [...new Set([...source.matchAll(HARDCODED_RE)].map((match) => match[0]))];
}

export async function auditTokenSource() {
  const css = await fs.readFile(TOKEN_FILE, "utf8");
  const tokenAudit = auditTokenText(css);

  const files = (await fs.readdir(UI_DIR)).filter((name) => name.endsWith(".tsx"));
  const hardcodedUsages = [];
  for (const file of files) {
    const source = await fs.readFile(path.join(UI_DIR, file), "utf8");
    const matches = findHardcodedColorClasses(source);
    if (matches.length) hardcodedUsages.push({ file, matches });
  }

  return {
    ...tokenAudit,
    hardcodedUsages,
  };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const result = await auditTokenSource();
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  if (result.duplicates.length) process.exitCode = 1;
}
