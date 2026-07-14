import { describe, expect, it } from "vitest";
import { sanitizeSvg } from "../sanitize-svg";

describe("sanitizeSvg", () => {
  it("strips script tags and event handlers from a mermaid SVG", () => {
    const dirty =
      '<svg><script>alert(1)</script><rect onclick="evil()" onload="evil()" x="0" /></svg>';

    const clean = sanitizeSvg(dirty);

    expect(clean).not.toContain("<script");
    expect(clean).not.toContain("onclick");
    expect(clean).not.toContain("onload");
    expect(clean).toContain("<svg");
  });

  it("preserves safe svg structure", () => {
    const safe =
      '<svg><rect x="0" y="0" width="10" height="10"><title>box</title></rect></svg>';

    const clean = sanitizeSvg(safe);

    expect(clean).toContain("<rect");
    expect(clean).toContain("<title>box</title>");
  });
});
