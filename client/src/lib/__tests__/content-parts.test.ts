import type { ThreadAssistantMessagePart } from "@assistant-ui/react";
import { describe, expect, it } from "vitest";

import { toDisplayContentParts } from "@/lib/content-parts";

describe("toDisplayContentParts", () => {
  it("converts local retrieved assets to blob URLs that Assistant UI accepts", async () => {
    const parts: ThreadAssistantMessagePart[] = [
      { text: "Figure 2", type: "text" },
      {
        filename: "bert.pdf",
        image: "/api/v1/documents/doc-1/assets/162.png",
        type: "image",
      },
      {
        id: "ev-1",
        mediaType: "image/png",
        sourceType: "document",
        title: "bert.pdf",
        type: "source",
      },
    ];

    const fetcher = (input: string | URL | Request) => {
      expect(String(input)).toBe(
        "http://localhost:5173/api/v1/documents/doc-1/assets/162.png"
      );
      return Promise.resolve(
        new Response(new Blob(["image"]), { status: 200 })
      );
    };

    await expect(
      toDisplayContentParts(parts, {
        createObjectUrl: () => "blob:http://localhost:5173/retrieved-figure",
        fetcher,
        origin: "http://localhost:5173",
      })
    ).resolves.toEqual([
      {
        filename: "bert.pdf",
        image: "blob:http://localhost:5173/retrieved-figure",
        type: "image",
      },
      { text: "Figure 2", type: "text" },
    ]);
  });
});
