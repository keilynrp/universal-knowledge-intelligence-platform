/**
 * Task 1.1 — enumerate candidate user-facing string literals in backend/.
 *
 * Deliberately over-inclusive: this produces the list a human then reads. It
 * must NOT decide anything, because deciding by pattern is exactly how the two
 * earlier counts (96/17 and 71/16) disagreed and both admitted docstrings that
 * merely contain an accented word.
 *
 * Emits: file, line, whether the literal is a docstring, and the text.
 */
const fs = require("fs");
const path = require("path");

const ROOT = "D:/universal-knowledge-intelligence-platform/backend";
const SKIP = new Set(["__pycache__", "tests", "alembic", "openalex_lake"]);

const ACCENT = /[áéíóúüñ¿¡ÁÉÍÓÚÜÑ]/;
const ES_WORDS = /\b(?:el|la|los|las|un|una|unos|unas|del|con|para|por|como|este|esta|estos|estas|que|sin|sobre|entre|desde|hasta|segun|según|puede|debe|antes|cada|todos|todas|otro|otra|no|se|su|sus|es|son|hay|más|más)\b/gi;

function walk(dir, acc = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.isDirectory()) { if (!SKIP.has(e.name)) walk(path.join(dir, e.name), acc); }
    else if (e.name.endsWith(".py")) acc.push(path.join(dir, e.name));
  }
  return acc;
}

const rows = [];
for (const file of walk(ROOT)) {
  const src = fs.readFileSync(file, "utf8");
  const rel = "backend/" + path.relative(ROOT, file).replace(/\\/g, "/");

  // Triple-quoted first (so they are not re-matched as single-quoted), then simple.
  const re = /(?:(?:[fru]{0,2})("""|''')([\s\S]*?)\1)|(?:[fru]{0,2}"((?:[^"\\\n]|\\.)*)")|(?:[fru]{0,2}'((?:[^'\\\n]|\\.)*)')/g;
  let m;
  while ((m = re.exec(src))) {
    const isDoc = Boolean(m[1]);
    const text = (m[2] ?? m[3] ?? m[4] ?? "").trim();
    if (text.length < 8) continue;

    const accent = ACCENT.test(text);
    const words = (text.match(ES_WORDS) || []).length;
    if (!accent && words < 2) continue;

    const line = src.slice(0, m.index).split("\n").length;
    rows.push({ file: rel, line, isDoc, text: text.replace(/\s+/g, " ") });
  }
}

rows.sort((a, b) => a.file.localeCompare(b.file) || a.line - b.line);

const byFile = new Map();
rows.forEach((r) => byFile.set(r.file, (byFile.get(r.file) || 0) + 1));

console.log(`candidates: ${rows.length} across ${byFile.size} files`);
console.log(`(docstring-shaped: ${rows.filter((r) => r.isDoc).length}, inline: ${rows.filter((r) => !r.isDoc).length})\n`);

let current = "";
for (const r of rows) {
  if (r.file !== current) { current = r.file; console.log(`\n### ${current}`); }
  const tag = r.isDoc ? "DOC " : "STR ";
  console.log(`  ${tag}${String(r.line).padStart(4)}  ${r.text.slice(0, 110)}`);
}

fs.writeFileSync(process.argv[2], JSON.stringify(rows, null, 2));
