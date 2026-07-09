import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router";

const ChatPage = lazy(() =>
  import("@/pages/chat.tsx").then((m) => ({ default: m.ChatPage }))
);

import { HomePage } from "@/pages/home.tsx";

export function App() {
  return (
    <Suspense fallback={null}>
      <Routes>
        <Route element={<HomePage />} index />
        <Route element={<ChatPage />} path="chat" />
        <Route element={<ChatPage />} path="chat/:threadId" />
      </Routes>
    </Suspense>
  );
}
