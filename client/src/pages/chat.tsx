import {
  AssistantRuntimeProvider,
  useAui,
  useAuiState,
} from "@assistant-ui/react";
import { AuiProvider } from "@assistant-ui/store";
import {
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import { Thread } from "@/components/assistant-ui/thread";
import { Header } from "@/components/chat/chat-header";
import { AppShell, useSidebarState } from "@/components/chat/chat-sidebar";
import {
  EvidencePanelProvider,
  useEvidencePanel,
} from "@/components/chat/evidence-context";
import { EvidenceSidepanel } from "@/components/chat/evidence-sidepanel";
import { useEvidentRuntime } from "@/hooks/use-evident-runtime";
import { getMessageEvidence } from "@/lib/evidence-store";
import { cn } from "@/lib/utils";

const ChatLayout = () => {
  const { collapsed: sidebarCollapsed, setCollapsed: setSidebarCollapsed } =
    useSidebarState();
  const [panelDismissed, setPanelDismissed] = useState(true);
  const { clearEvidence, selectedEvidenceIds, selectedMessageId } =
    useEvidencePanel();
  const threadId = useAuiState((s) => s.threads.mainThreadId ?? null);

  const evidence = useMemo(() => {
    if (!(threadId && selectedMessageId)) {
      return null;
    }
    return getMessageEvidence(selectedMessageId);
  }, [selectedMessageId, threadId]);

  const showPanel = evidence !== null && evidence.length > 0 && !panelDismissed;

  useEffect(() => {
    if (selectedEvidenceIds.length > 0) {
      setPanelDismissed(false);
    }
  }, [selectedEvidenceIds]);

  const handleClosePanel = useCallback(() => {
    setPanelDismissed(true);
    clearEvidence();
  }, [clearEvidence]);

  const handleToggleSidebar = useCallback(() => {
    setSidebarCollapsed((prev) => !prev);
  }, [setSidebarCollapsed]);

  return (
    <AppShell collapsed={sidebarCollapsed}>
      <div className="flex flex-1 flex-col overflow-hidden rounded-lg bg-background">
        <Header
          onToggleSidebar={handleToggleSidebar}
          sidebarCollapsed={sidebarCollapsed}
        />
        <div
          className={cn(
            "flex flex-1 overflow-hidden",
            !showPanel && "justify-center"
          )}
        >
          <main
            className={cn(
              "overflow-hidden",
              showPanel ? "flex-1" : "w-full max-w-4xl"
            )}
          >
            <Thread key={threadId ?? "no-thread"} />
          </main>
          <aside
            className={cn(
              "hidden min-w-0 items-stretch overflow-hidden py-2 pr-2 transition-[width] duration-300 ease-in-out md:flex",
              showPanel ? "w-96 shrink-0" : "w-0"
            )}
          >
            <EvidenceSidepanel
              activeEvidenceId={selectedEvidenceIds[0] ?? null}
              evidence={evidence}
              onClose={handleClosePanel}
              open={showPanel}
            />
          </aside>
        </div>
      </div>
    </AppShell>
  );
};

const ChatLayoutWrapper = () => {
  const { runtime } = useEvidentRuntime();

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <EvidencePanelProvider>
        <ChatLayout />
      </EvidencePanelProvider>
    </AssistantRuntimeProvider>
  );
};

const AuiProviderWrapper = ({ children }: { children: ReactNode }) => {
  const rootClient = useAui({}, { parent: null });

  return <AuiProvider value={rootClient}>{children}</AuiProvider>;
};

export const ChatPage = () => (
  <AuiProviderWrapper>
    <ChatLayoutWrapper />
  </AuiProviderWrapper>
);
