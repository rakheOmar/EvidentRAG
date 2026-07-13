import "@testing-library/jest-dom/vitest";

import { afterEach, beforeEach, vi } from "vitest";

function noop() {
  // Test stub.
}

function isStructuredApiLog(value: unknown): boolean {
  return (
    typeof value === "object" &&
    value !== null &&
    "event" in value &&
    (value as { event?: unknown }).event === "api_request_completed"
  );
}

beforeEach(() => {
  const originalInfo = console.info.bind(console);
  vi.spyOn(console, "info").mockImplementation((...args: unknown[]) => {
    if (args.some(isStructuredApiLog)) {
      return;
    }
    originalInfo(...args);
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

Object.defineProperty(window, "matchMedia", {
  value: (query: string) => ({
    addEventListener: noop,
    addListener: noop,
    dispatchEvent: () => false,
    matches: false,
    media: query,
    onchange: null,
    removeEventListener: noop,
    removeListener: noop,
  }),
  writable: true,
});

class ResizeObserverStub {
  disconnect = noop;

  observe = noop;

  unobserve = noop;
}

window.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;
