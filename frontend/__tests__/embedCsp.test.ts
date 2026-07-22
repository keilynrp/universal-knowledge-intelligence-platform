/**
 * Per-widget frame-ancestors derivation for the embed page.
 *
 * Spec: openspec/changes/fix-embed-widget-distribution — "Embed routes are
 * framable, the rest of the app is not."
 */
import { describe, expect, it } from "vitest";
import { buildFrameAncestors, buildEmbedCsp } from "../lib/embedCsp";

describe("buildFrameAncestors", () => {
  it("maps * to any ancestor", () => {
    expect(buildFrameAncestors("*")).toBe("frame-ancestors *");
  });

  it("lists exactly the configured origins", () => {
    expect(
      buildFrameAncestors("https://a.example.com, https://b.example.com"),
    ).toBe("frame-ancestors https://a.example.com https://b.example.com");
  });

  it("ignores empty segments from sloppy comma usage", () => {
    expect(buildFrameAncestors("https://a.example.com,,  ,")).toBe(
      "frame-ancestors https://a.example.com",
    );
  });

  it("fails closed on unknown input", () => {
    // If we cannot know who may frame the widget, nobody may. A restricted
    // widget must never become open because a config fetch failed.
    expect(buildFrameAncestors(null)).toBe("frame-ancestors 'none'");
    expect(buildFrameAncestors("")).toBe("frame-ancestors 'none'");
    expect(buildFrameAncestors("   ")).toBe("frame-ancestors 'none'");
  });

  it("drops origins that are not http(s)", () => {
    // A stored value like "javascript:" or a bare word must not end up in a
    // response header.
    expect(
      buildFrameAncestors("javascript:alert(1), https://ok.example.com"),
    ).toBe("frame-ancestors https://ok.example.com");
  });

  it("strips characters that could split the header", () => {
    expect(buildFrameAncestors("https://a.example.com\nX-Evil: 1")).toBe(
      "frame-ancestors 'none'",
    );
  });
});

describe("buildEmbedCsp", () => {
  it("embeds the frame-ancestors directive in a full policy", () => {
    const csp = buildEmbedCsp("*", "https://api.ukip.example.com");
    expect(csp).toContain("frame-ancestors *");
    expect(csp).toContain("default-src 'self'");
    expect(csp).toContain("connect-src 'self' https://api.ukip.example.com");
  });

  it("never contains 'frame-ancestors 'none'' alongside real origins", () => {
    const csp = buildEmbedCsp("https://a.example.com", "https://api.x.com");
    expect(csp).toContain("frame-ancestors https://a.example.com");
    expect(csp).not.toContain("'none'");
  });
});
