import { describe, expect, it } from "vitest";
import { auditTokenSource } from "../scripts/audit-design-tokens.mjs";

describe("design-token audit", () => {
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
