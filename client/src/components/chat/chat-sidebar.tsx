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
  <div className="flex items-center justify-center font-medium text-sm">
    <img
      alt="EvidentRAG"
      className="h-7 w-auto"
      height={28}
      src="/brand/logo-transparent.png"
      width={112}
    />
  </div>
);

const Sidebar: FC<{ collapsed?: boolean }> = ({ collapsed }) => (
  <aside
    className={cn(
      "flex h-full flex-col overflow-hidden transition-[width] duration-200",
      collapsed ? "w-12" : "w-65"
    )}
  >
    <div
      className={cn(
        "mt-2 flex h-12 shrink-0 items-center justify-center transition-[padding] duration-200",
        collapsed ? "px-0" : "px-6"
      )}
    >
      {collapsed ? (
        <img
          alt="EvidentRAG"
          className="size-6 object-contain"
          height={24}
          src="/brand/icon-transparent.png"
          width={24}
        />
      ) : (
        <img
          alt="EvidentRAG"
          className="h-7 w-auto"
          height={28}
          src="/brand/logo-transparent.png"
          width={112}
        />
      )}
    </div>
    <ThreadListRoot
      className={cn(
        "relative flex-1 overflow-y-auto transition-[padding,width] duration-200",
        collapsed ? "w-12 px-2 pt-1" : "w-65 p-3"
      )}
    >
      {collapsed ? (
        <ThreadListNew
          className="w-8 gap-0 overflow-hidden px-2 transition-[width,padding,gap] duration-200 has-[>svg]:px-2"
          labelClassName="max-w-0 overflow-hidden opacity-0 transition-[max-width,opacity] duration-200"
          title="New Query"
        />
      ) : (
        <Tooltip>
          <TooltipTrigger
            render={
              <ThreadListNew
                className="w-full gap-2 overflow-hidden px-2.5 transition-[width,padding,gap] duration-200 has-[>svg]:px-2.5"
                labelClassName="max-w-24 overflow-hidden opacity-100 transition-[max-width,opacity] duration-200"
              />
            }
          />
          <TooltipContent side="right">New Query</TooltipContent>
        </Tooltip>
      )}
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
      <div className="flex h-12 shrink-0 items-center justify-center px-4">
        <Logo />
      </div>
      <div className="relative flex-1 overflow-y-auto p-3">
        <ThreadList />
      </div>
    </SheetContent>
  </Sheet>
);

export { Logo, MobileSidebar, Sidebar };
