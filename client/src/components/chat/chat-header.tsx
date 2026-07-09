"use client";

import { useAuiState } from "@assistant-ui/react";
import { PanelLeftIcon, ShareIcon } from "lucide-react";
import { type FC, memo } from "react";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import { MobileSidebar } from "./chat-sidebar";

const ThreadTitle: FC = () => {
  const title = useAuiState(
    (s) =>
      s.threads.threadItems.find((t) => t.id === s.threads.mainThreadId)?.title
  );

  return (
    <span className="min-w-0 truncate font-medium text-sm">
      {title ?? "New Chat"}
    </span>
  );
};

const Header = memo(function Header({
  sidebarCollapsed,
  onToggleSidebar,
}: {
  sidebarCollapsed: boolean;
  onToggleSidebar: () => void;
}) {
  return (
    <header className="flex h-12 shrink-0 items-center gap-2 px-4">
      <MobileSidebar />
      <TooltipIconButton
        className="hidden size-8 md:flex"
        onClick={onToggleSidebar}
        side="bottom"
        size="icon"
        tooltip={sidebarCollapsed ? "Show sidebar" : "Hide sidebar"}
        variant="ghost"
      >
        <PanelLeftIcon className="size-4" />
      </TooltipIconButton>
      <ThreadTitle />
      <TooltipIconButton
        className="ml-auto size-8"
        disabled
        side="bottom"
        size="icon"
        tooltip="Share"
        variant="ghost"
      >
        <ShareIcon className="size-4" />
      </TooltipIconButton>
    </header>
  );
});

export { Header, ThreadTitle };
