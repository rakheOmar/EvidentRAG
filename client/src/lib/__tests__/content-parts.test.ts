import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { toDisplayContentParts } from "../content-parts";

const ORIGIN = "http://example.test";

function makeFetcher() {
  return vi.fn(async () => ({
    ok: true,
    blob: async () => new Blob(["x"]),
  })) as unknown as typeof fetch;
}

describe("toDisplayContentParts image caching", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("reuses a cached image fetch within the TTL", async () => {
    const fetcher = makeFetcher();
    const options = {
      fetcher,
      createObjectUrl: () => "blob:x",
      origin: ORIGIN,
    };

    await toDisplayContentParts(
      [{ type: "image", image: "/asset/1.png" }],
      options
    );
    await toDisplayContentParts(
      [{ type: "image", image: "/asset/1.png" }],
      options
    );

    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("re-fetches an image after the cache TTL expires", async () => {
    vi.useFakeTimers();
    const fetcher = makeFetcher();
    const options = {
      fetcher,
      createObjectUrl: () => "blob:x",
      origin: ORIGIN,
    };

    await toDisplayContentParts(
      [{ type: "image", image: "/asset/2.png" }],
      options
    );
    expect(fetcher).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(6 * 60 * 1000);

    await toDisplayContentParts(
      [{ type: "image", image: "/asset/2.png" }],
      options
    );
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});
