import type { ThreadAssistantMessagePart } from "@assistant-ui/react";
import { describe, expect, it, vi } from "vitest";

import { toDisplayContentParts } from "@/lib/content-parts";

describe("toDisplayContentParts", () => {
  it("resolves local images, removes sources, and keeps images before text", async () => {
    const parts: ThreadAssistantMessagePart[] = [
      { text: "Figure 2", type: "text" },
      {
        filename: "bert.pdf",
        image: "/api/v1/documents/doc-content-order/assets/162.png",
        type: "image",
      },
      {
        id: "ev-content-order",
        mediaType: "image/png",
        sourceType: "document",
        title: "bert.pdf",
        type: "source",
      },
    ];
    const fetcher = vi
      .fn()
      .mockResolvedValue(new Response(new Blob(["image"]), { status: 200 }));

    await expect(
      toDisplayContentParts(parts, {
        createObjectUrl: () => "blob:http://localhost/retrieved-figure",
        fetcher,
        origin: "http://localhost:5173",
      })
    ).resolves.toEqual([
      {
        filename: "bert.pdf",
        image: "blob:http://localhost/retrieved-figure",
        type: "image",
      },
      { text: "Figure 2", type: "text" },
    ]);

    expect(fetcher).toHaveBeenCalledWith(
      "http://localhost:5173/api/v1/documents/doc-content-order/assets/162.png"
    );
  });

  it.each([
    "blob:http://localhost/already-blob",
    "https://cdn.example.test/already-public.png",
  ])("passes %s through without fetching", async (image) => {
    const fetcher = vi.fn();

    await expect(
      toDisplayContentParts(
        [{ filename: "figure.png", image, type: "image" }],
        { fetcher, origin: "http://localhost:5173" }
      )
    ).resolves.toEqual([{ filename: "figure.png", image, type: "image" }]);

    expect(fetcher).not.toHaveBeenCalled();
  });

  it("does not cache a failed image load", async () => {
    const image = "/api/v1/documents/doc-retry/assets/1.png";
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(new Response("missing", { status: 404 }))
      .mockResolvedValueOnce(
        new Response(new Blob(["image"]), { status: 200 })
      );
    const options = {
      createObjectUrl: () => "blob:http://localhost/retry",
      fetcher,
      origin: "http://localhost:5173",
    };

    await expect(
      toDisplayContentParts([{ image, type: "image" }], options)
    ).rejects.toThrow("Unable to load retrieved image (404)");
    await expect(
      toDisplayContentParts([{ image, type: "image" }], options)
    ).resolves.toEqual([{ image: options.createObjectUrl(), type: "image" }]);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("deduplicates concurrent loads for the same local image", async () => {
    const image = "/api/v1/documents/doc-dedupe/assets/1.png";
    const fetcher = vi
      .fn()
      .mockResolvedValue(new Response(new Blob(["image"]), { status: 200 }));
    const options = {
      createObjectUrl: () => "blob:http://localhost/dedupe",
      fetcher,
      origin: "http://localhost:5173",
    };

    const [first, second] = await Promise.all([
      toDisplayContentParts([{ image, type: "image" }], options),
      toDisplayContentParts([{ image, type: "image" }], options),
    ]);

    expect(first).toEqual([
      { image: options.createObjectUrl(), type: "image" },
    ]);
    expect(second).toEqual(first);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
