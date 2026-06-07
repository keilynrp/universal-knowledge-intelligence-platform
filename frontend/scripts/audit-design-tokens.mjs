import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const TOKEN_FILE = path.join(ROOT, "app", "styles", "tokens.css");
const UI_DIR = path.join(ROOT, "app", "components", "ui");
const TOKEN_RE = /^\s*(--ukip-[a-z0-9-]+):/gm;
const HARDCODED_RE =
  /\b(?:bg|text|border|ring|shadow)-(?:gray|slate|red|amber|yellow|green|emerald|blue|cyan|violet|purple)-[0-9]+(?:\/[0-9]+)?/g;

export async function auditTokenSource() {
  const css = await fs.readFile(TOKEN_FILE, "utf8");
  const declarations = [...css.matchAll(TOKEN_RE)].map((match) => match[1]);
  const counts = new Map();
  for (const token of declarations) counts.set(token, (counts.get(token) ?? 0) + 1);

  const files = (await fs.readdir(UI_DIR)).filter((name) => name.endsWith(".tsx"));
  const hardcodedUsages = [];
  for (const file of files) {
    const source = await fs.readFile(path.join(UI_DIR, file), "utf8");
    const matches = [...source.matchAll(HARDCODED_RE)].map((match) => match[0]);
    if (matches.length) hardcodedUsages.push({ file, matches: [...new Set(matches)] });
  }

  return {
    declarations: [...new Set(declarations)].sort(),
    duplicates: [...counts].filter(([, count]) => count > 2).map(([name]) => name),
    hardcodedUsages,
  };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const result = await auditTokenSource();
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  if (result.duplicates.length) process.exitCode = 1;
}
