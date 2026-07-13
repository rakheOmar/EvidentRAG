import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router";

const ChatPage = lazy(() =>
  import("@/pages/chat.tsx").then((m) => ({ default: m.ChatPage }))
);
const DocumentsPage = lazy(() =>
  import("@/pages/documents.tsx").then((m) => ({ default: m.DocumentsPage }))
);

import { HomePage } from "@/pages/home.tsx";
import { SidebarStateProvider } from "@/components/chat/chat-sidebar";

export function App() {
  return (
    <SidebarStateProvider>
      <Suspense fallback={null}>
        <Routes>
          <Route element={<HomePage />} index />
          <Route element={<ChatPage />} path="chat" />
          <Route element={<ChatPage />} path="chat/:threadId" />
          <Route element={<DocumentsPage />} path="documents" />
        </Routes>
      </Suspense>
    </SidebarStateProvider>
  );
}
