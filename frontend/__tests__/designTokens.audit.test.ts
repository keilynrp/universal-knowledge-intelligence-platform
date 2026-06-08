import { readFile } from "node:fs/promises";
import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  auditTokenSource,
  auditTokenText,
  findHardcodedColorClasses,
} from "../scripts/audit-design-tokens.mjs";

const semanticStateTokens = [
  "--ukip-success",
  "--ukip-success-soft",
  "--ukip-warning-soft",
  "--ukip-danger-soft",
  "--ukip-info",
  "--ukip-info-soft",
];

describe("design-token audit", () => {
  it("allows one declaration per token in root and dark scopes", () => {
    const result = auditTokenText(`
      :root { --ukip-bg: white; }
      .dark { --ukip-bg: black; }
    `);

    expect(result.duplicates).toEqual([]);
  });

  it("flags a token repeated within the same scope", () => {
    const result = auditTokenText(`
      :root {
        --ukip-space-4: 1rem;
        --ukip-space-4: 16px;
      }
    `);

    expect(result.duplicates).toEqual(["--ukip-space-4"]);
  });

  it("ignores commented-out token declarations", () => {
    const result = auditTokenText(`
      :root {
        --ukip-bg: white;
        /*
        --ukip-bg: oldlace;
        */
      }
    `);

    expect(result.declarations).toEqual(["--ukip-bg"]);
    expect(result.duplicates).toEqual([]);
  });

  it("detects gradient, fill, and stroke color utilities", () => {
    const matches = findHardcodedColorClasses(
      "from-violet-500 via-cyan-400 to-blue-600 fill-red-500 stroke-emerald-600",
    );

    expect(matches).toEqual([
      "from-violet-500",
      "via-cyan-400",
      "to-blue-600",
      "fill-red-500",
      "stroke-emerald-600",
    ]);
  });

  it("ignores non-color and layout utilities", () => {
    const matches = findHardcodedColorClasses(
      "bg-cover text-sm border-2 ring-2 shadow-lg fill-current stroke-2 from-20% divide-x",
    );

    expect(matches).toEqual([]);
  });

  it("requires a complete Tailwind color class boundary", () => {
    const matches = findHardcodedColorClasses(
      "text-red-500ish bg-blue-600_button text-red-500 bg-blue-600/20",
    );

    expect(matches).toEqual(["text-red-500", "bg-blue-600/20"]);
  });

  it("declares each semantic state token once in root and dark scopes", async () => {
    const css = await readFile(
      path.join(process.cwd(), "app", "styles", "tokens.css"),
      "utf8",
    );
    const rootScope = css.match(/:root\s*\{([^}]*)\}/)?.[1];
    const darkScope = css.match(/\.dark\s*\{([^}]*)\}/)?.[1];

    expect(rootScope).toBeDefined();
    expect(darkScope).toBeDefined();

    for (const scope of [rootScope!, darkScope!]) {
      const result = auditTokenText(`.scope {${scope}}`);

      expect(result.declarations).toEqual(
        expect.arrayContaining(semanticStateTokens),
      );
      expect(result.duplicates).toEqual([]);
    }
  });

  it("reports declarations, duplicates, and hardcoded UI color families", async () => {
    const result = await auditTokenSource();

    expect(result.declarations).toContain("--ukip-bg");
    expect(result.declarations).toContain("--ukip-space-4");
    expect(result.declarations).toEqual(
      expect.arrayContaining([
        "--ukip-success-soft",
        "--ukip-warning-soft",
        "--ukip-danger-soft",
        "--ukip-info",
        "--ukip-info-soft",
      ]),
    );
    expect(result.duplicates).toEqual([]);
    expect(result.hardcodedUsages).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ file: expect.stringContaining("Badge.tsx") }),
      ]),
    );
  });
});
