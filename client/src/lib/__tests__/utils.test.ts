import { describe, expect, it } from "vitest";

import { cn } from "../utils";

describe("cn", () => {
	it("merges class names", () => {
		expect(cn("px-4", "py-2")).toBe("px-4 py-2");
	});

	it("handles conditional classes", () => {
		expect(cn("base", false, "visible")).toBe("base visible");
	});

	it("resolves tailwind conflicts", () => {
		expect(cn("px-4", "px-2")).toBe("px-2");
	});
});
