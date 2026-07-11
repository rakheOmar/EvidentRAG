import { describe, expect, it, vi } from "vitest";

import { ApiError, classifyError, requestJson } from "@/lib/errors";

describe("error presentation", () => {
  it("keeps validation errors inline", () => {
    expect(classifyError(422)).toBe("inline");
    expect(classifyError(400)).toBe("inline");
  });

  it("uses toast for recoverable resource errors", () => {
    expect(classifyError(404)).toBe("toast");
    expect(classifyError(409)).toBe("toast");
  });

  it("uses dialog for blocking failures", () => {
    expect(classifyError(503)).toBe("dialog");
    expect(new ApiError("down", 503).presentation).toBe("dialog");
  });

  it("parses the server error envelope", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          error: {
            code: "validation_error",
            details: { fields: [{ loc: ["body", "content"] }] },
            message: "Content is required",
            request_id: "req-1",
          },
        }),
        { status: 422 },
      ),
    );
    vi.stubGlobal("fetch", fetcher);

    await expect(requestJson("/api/v1/threads", { method: "POST" })).rejects.toMatchObject({
      code: "validation_error",
      message: "Content is required",
      presentation: "inline",
      requestId: "req-1",
      status: 422,
    });
    vi.unstubAllGlobals();
  });
});
