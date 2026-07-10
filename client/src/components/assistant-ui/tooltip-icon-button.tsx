"use client";

import { type ComponentPropsWithRef, forwardRef } from "react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export type TooltipIconButtonProps = ComponentPropsWithRef<typeof Button> & {
  tooltip: string;
  side?: "top" | "bottom" | "left" | "right";
};

export const TooltipIconButton = forwardRef<
  HTMLButtonElement,
  TooltipIconButtonProps
>(({ children, tooltip, side = "bottom", className, ...rest }, ref) => (
  <TooltipProvider delay={0}>
    <Tooltip>
      <TooltipTrigger
        render={
          <Button
            size="icon"
            variant="ghost"
            {...rest}
            className={cn(
              "aui-button-icon size-8 p-0 active:scale-96",
              className,
            )}
            ref={ref}
          >
            {children}
            <span className="aui-sr-only sr-only">{tooltip}</span>
          </Button>
        }
      />
      <TooltipContent side={side}>{tooltip}</TooltipContent>
    </Tooltip>
  </TooltipProvider>
));

TooltipIconButton.displayName = "TooltipIconButton";
