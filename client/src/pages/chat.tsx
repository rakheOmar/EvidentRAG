import { AssistantRuntimeProvider, useAui } from "@assistant-ui/react";
import { AuiProvider } from "@assistant-ui/store";
import { type ReactNode, useState } from "react";
import { Thread } from "@/components/assistant-ui/thread";
import { Header } from "@/components/chat/chat-header";
import { Sidebar } from "@/components/chat/chat-sidebar";
import { useEvidentRuntime } from "@/hooks/use-evident-runtime";

const ChatLayout = () => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  return (
    <div className="flex h-full w-full bg-muted/30">
      <div className="hidden md:block">
        <Sidebar collapsed={sidebarCollapsed} />
      </div>
      <div className="flex flex-1 flex-col overflow-hidden p-2 md:pl-0">
        <div className="flex flex-1 flex-col overflow-hidden rounded-lg bg-background">
          <Header
            onToggleSidebar={() => setSidebarCollapsed(!sidebarCollapsed)}
            sidebarCollapsed={sidebarCollapsed}
          />
          <main className="flex-1 overflow-hidden">
            <Thread />
          </main>
        </div>
      </div>
    </div>
  );
};

const RuntimeShell = () => {
  const { runtime } = useEvidentRuntime();

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ChatLayout />
    </AssistantRuntimeProvider>
  );
};

const AuiProviderWrapper = ({ children }: { children: ReactNode }) => {
  const rootClient = useAui({}, { parent: null });

  return <AuiProvider value={rootClient}>{children}</AuiProvider>;
};

export const ChatPage = () => (
  <AuiProviderWrapper>
    <RuntimeShell />
  </AuiProviderWrapper>
);
