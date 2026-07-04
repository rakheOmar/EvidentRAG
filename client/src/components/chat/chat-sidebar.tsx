"use client";

import { MenuIcon } from "lucide-react";
import type { FC } from "react";
import {
  ThreadList,
  ThreadListItems,
  ThreadListNew,
  ThreadListRoot,
} from "@/components/assistant-ui/thread-list";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

const Logo: FC = () => (
  <div className="flex items-center gap-2 px-2 font-medium text-sm">
    <span className="text-foreground/90">EvidentRAG</span>
  </div>
);

const Sidebar: FC<{ collapsed?: boolean }> = ({ collapsed }) => (
  <aside
    className={cn(
      "flex h-full flex-col overflow-hidden transition-all duration-200",
      collapsed ? "w-12" : "w-65"
    )}
  >
    <div
      className={cn(
        "mt-2 flex h-12 shrink-0 items-center transition-[padding] duration-200",
        collapsed ? "px-3.5" : "px-6"
      )}
    >
      <span
        className={cn(
          "ml-2 whitespace-nowrap font-medium text-foreground/90 text-sm transition-opacity duration-200",
          collapsed && "opacity-0"
        )}
      >
        EvidentRAG
      </span>
    </div>
    <ThreadListRoot
      className={cn(
        "relative flex-1 overflow-y-auto transition-[padding,width] duration-200",
        collapsed ? "w-12 px-2 pt-1" : "w-65 p-3"
      )}
    >
      <Tooltip>
        <TooltipTrigger
          render={
            <ThreadListNew
              className={cn(
                "overflow-hidden transition-all duration-200",
                collapsed
                  ? "w-8 gap-0 px-2 has-[>svg]:px-2"
                  : "w-full gap-2 px-2.5 has-[>svg]:px-2.5"
              )}
              labelClassName={cn(
                "overflow-hidden transition-all duration-200",
                collapsed ? "max-w-0 opacity-0" : "max-w-24 opacity-100"
              )}
            />
          }
        />
        {collapsed && <TooltipContent side="right">New Query</TooltipContent>}
      </Tooltip>
      <ThreadListItems
        aria-hidden={collapsed}
        className={cn(
          "transition-[opacity,transform] duration-150",
          collapsed
            ? "pointer-events-none opacity-0 delay-50"
            : "translate-x-0 opacity-100"
        )}
        inert={collapsed}
      />
    </ThreadListRoot>
  </aside>
);

const MobileSidebar: FC = () => (
  <Sheet>
    <SheetTrigger
      render={
        <Button
          className="size-8 shrink-0 md:hidden"
          size="icon"
          variant="ghost"
        >
          <MenuIcon className="size-4" />
          <span className="sr-only">Toggle menu</span>
        </Button>
      }
    />
    <SheetContent className="flex w-70 flex-col p-0" side="left">
      <div className="flex h-12 shrink-0 items-center px-4">
        <Logo />
      </div>
      <div className="relative flex-1 overflow-y-auto p-3">
        <ThreadList />
      </div>
    </SheetContent>
  </Sheet>
);

export { Logo, MobileSidebar, Sidebar };
