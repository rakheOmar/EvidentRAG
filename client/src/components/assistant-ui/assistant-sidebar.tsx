import type { FC, PropsWithChildren } from "react";
import { Thread } from "@/components/assistant-ui/thread";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";

export const AssistantSidebar: FC<PropsWithChildren> = ({ children }) => (
  <ResizablePanelGroup orientation="horizontal">
    <ResizablePanel>{children}</ResizablePanel>
    <ResizableHandle />
    <ResizablePanel>
      <Thread />
    </ResizablePanel>
  </ResizablePanelGroup>
);
