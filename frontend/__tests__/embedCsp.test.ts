/**
 * Per-widget frame-ancestors derivation for the embed page.
 *
 * Spec: openspec/changes/fix-embed-widget-distribution — "Embed routes are
 * framable, the rest of the app is not."
 */
import { describe, expect, it } from "vitest";
import { buildFrameAncestors, buildEmbedCsp, isWidgetToken } from "../lib/embedCsp";

describe("isWidgetToken", () => {
  it("accepts a UUID4, the format the backend mints", () => {
    expect(isWidgetToken("00000000-0000-4000-8000-000000000000")).toBe(true);
  });

  it("is case-insensitive", () => {
    expect(isWidgetToken("AAAAAAAA-BBBB-4CCC-8DDD-EEEEEEEEEEEE")).toBe(true);
  });

  it("rejects path traversal", () => {
    // The token is interpolated into a server-side fetch URL. Without this,
    // a crafted token reaches other backend paths (CodeQL js/request-forgery).
    expect(isWidgetToken("../admin/data-lifecycle/purge")).toBe(false);
    expect(isWidgetToken("..%2f..%2fhealth")).toBe(false);
  });

  it("rejects anything with URL structure", () => {
    expect(isWidgetToken("http://evil.example.com")).toBe(false);
    expect(isWidgetToken("evil.example.com/x")).toBe(false);
    expect(isWidgetToken("a?b=c")).toBe(false);
    expect(isWidgetToken("a#b")).toBe(false);
  });

  it("rejects empty and malformed values", () => {
    expect(isWidgetToken("")).toBe(false);
    expect(isWidgetToken("not-a-uuid")).toBe(false);
    expect(isWidgetToken("00000000000040008000000000000000")).toBe(false);
  });
});

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
