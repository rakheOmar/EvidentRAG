"use client";

import { AssistantRuntimeProvider, useAui } from "@assistant-ui/react";
import { AuiProvider } from "@assistant-ui/store";
import { type ReactNode, useMemo, useState } from "react";
import { Header } from "@/components/chat/chat-header";
import { Sidebar } from "@/components/chat/chat-sidebar";
import { Thread } from "@/components/chat/chat-thread";
import { EvidencePanel } from "@/components/chat/evidence-panel";
import {
  EvidenceSelectionProvider,
  useEvidenceSelection,
} from "@/components/chat/evidence-selection";
import { EvidentMessagesProvider } from "@/components/chat/evident-messages";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import { useEvidentRuntime } from "@/hooks/use-evident-runtime";
import { type EvidentChatMessage, isAnswerDetail } from "@/lib/types";

interface ChatLayoutProps {
  messages: EvidentChatMessage[];
}

const ChatLayout = ({ messages }: ChatLayoutProps) => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const { selectedEvidenceId } = useEvidenceSelection();

  const currentAnswer = useMemo(() => {
    for (const message of [...messages].reverse()) {
      if (message.role === "assistant" && isAnswerDetail(message.answer)) {
        return message.answer;
      }
    }

    return null;
  }, [messages]);

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
            <ResizablePanelGroup orientation="horizontal">
              <ResizablePanel defaultSize={70} minSize={50}>
                <Thread />
              </ResizablePanel>
              <ResizableHandle withHandle />
              <ResizablePanel defaultSize={30} minSize={20}>
                <EvidencePanel
                  answer={currentAnswer}
                  selectedEvidenceId={selectedEvidenceId}
                />
              </ResizablePanel>
            </ResizablePanelGroup>
          </main>
        </div>
      </div>
    </div>
  );
};

const RuntimeShell = () => {
  const { messages, runtime } = useEvidentRuntime();

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <EvidentMessagesProvider messages={messages}>
        <EvidenceSelectionProvider>
          <ChatLayout messages={messages} />
        </EvidenceSelectionProvider>
      </EvidentMessagesProvider>
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
