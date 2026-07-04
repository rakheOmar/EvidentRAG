import "@testing-library/jest-dom/vitest";

function noop() {
  // Test stub.
}

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
