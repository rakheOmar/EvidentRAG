import { Route, Routes } from "react-router";

import { ChatPage } from "@/pages/chat.tsx";
import { HomePage } from "@/pages/home.tsx";

export function App() {
  return (
    <Routes>
      <Route element={<HomePage />} index />
      <Route element={<ChatPage />} path="chat" />
    </Routes>
  );
}

export default App;
