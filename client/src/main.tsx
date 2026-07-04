import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";

import "./index.css";
import { ThemeProvider } from "@/components/theme-provider.tsx";
import { TooltipProvider } from "@/components/ui/tooltip";

import App from "./app.tsx";

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
