const origAddEventListener = EventTarget.prototype.addEventListener;
EventTarget.prototype.addEventListener = function (
  type: string,
  listener: EventListenerOrEventListenerObject | null,
  options?: boolean | AddEventListenerOptions
) {
  let opts = options;
  if (type === "touchstart" || type === "touchmove") {
    if (opts === undefined || opts === null) {
      opts = { passive: true } as AddEventListenerOptions;
    } else if (typeof opts === "boolean") {
      opts = { capture: opts, passive: true };
    } else if (!(opts as AddEventListenerOptions).passive) {
      opts = { ...(opts as AddEventListenerOptions), passive: true };
    }
  }
  return origAddEventListener.call(this, type, listener, opts);
};

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";

import "./index.css";
import { ThemeProvider } from "@/components/theme-provider.tsx";
import { TooltipProvider } from "@/components/ui/tooltip";

import { App } from "./app.tsx";

const queryClient = new QueryClient();
const rootElement = document.querySelector("#root");

if (!(rootElement instanceof HTMLElement)) {
  throw new Error("Root element '#root' was not found.");
}

createRoot(rootElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ThemeProvider>
          <TooltipProvider>
            <App />
          </TooltipProvider>
        </ThemeProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>
);
