import { describe, expect, it } from "vitest";
import {
  auditTokenSource,
  auditTokenText,
  findHardcodedColorClasses,
} from "../scripts/audit-design-tokens.mjs";

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

  it("reports declarations, duplicates, and hardcoded UI color families", async () => {
    const result = await auditTokenSource();

    expect(result.declarations).toContain("--ukip-bg");
    expect(result.declarations).toContain("--ukip-space-4");
    expect(result.duplicates).toEqual([]);
    expect(result.hardcodedUsages).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ file: expect.stringContaining("Badge.tsx") }),
      ]),
    );
  });
});
