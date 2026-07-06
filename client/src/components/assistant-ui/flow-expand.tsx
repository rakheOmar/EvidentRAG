"use client";

import { Maximize2, Minus, Plus, RotateCcw, X } from "lucide-react";
import {
  type ComponentProps,
  type PointerEvent,
  type ReactNode,
  useCallback,
  useRef,
  useState,
  type WheelEvent,
} from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

const MIN_SCALE = 0.5;
const MAX_SCALE = 4;

const flowControlButtonClass =
  "aui-flow-control size-7 cursor-pointer bg-muted/50 text-muted-foreground hover:bg-muted hover:text-foreground sm:size-8";

function clamp(n: number, min: number, max: number) {
  return Math.min(max, Math.max(min, n));
}

type FlowExpandProps = Omit<ComponentProps<"div">, "children"> & {
  children: ReactNode;
};

export function FlowExpand({ className, children, ...props }: FlowExpandProps) {
  const [open, setOpen] = useState(false);
  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 });
  const viewportRef = useRef<HTMLDivElement>(null);
  const drag = useRef<{
    startX: number;
    startY: number;
    originX: number;
    originY: number;
  } | null>(null);

  const onOpenChange = useCallback((nextOpen: boolean) => {
    setOpen(nextOpen);
    if (!nextOpen) {
      drag.current = null;
      setTransform({ x: 0, y: 0, scale: 1 });
    }
  }, []);

  const zoomBy = useCallback((factor: number, cx?: number, cy?: number) => {
    setTransform((current) => {
      const scale = clamp(current.scale * factor, MIN_SCALE, MAX_SCALE);
      const ratio = scale / current.scale;

      if (cx === undefined || cy === undefined) {
        const viewport = viewportRef.current;
        cx = (viewport?.clientWidth ?? 0) / 2;
        cy = (viewport?.clientHeight ?? 0) / 2;
      }

      return {
        scale,
        x: cx - (cx - current.x) * ratio,
        y: cy - (cy - current.y) * ratio,
      };
    });
  }, []);

  const onWheel = useCallback(
    (event: WheelEvent) => {
      const viewport = viewportRef.current;
      if (!viewport) {
        return;
      }

      const rect = viewport.getBoundingClientRect();
      zoomBy(
        Math.exp(-event.deltaY * 0.0015),
        event.clientX - rect.left,
        event.clientY - rect.top
      );
    },
    [zoomBy]
  );

  const onPointerDown = useCallback((event: PointerEvent) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    setTransform((current) => {
      drag.current = {
        startX: event.clientX,
        startY: event.clientY,
        originX: current.x,
        originY: current.y,
      };
      return current;
    });
  }, []);

  const onPointerMove = useCallback((event: PointerEvent) => {
    const currentDrag = drag.current;
    if (!currentDrag) {
      return;
    }

    setTransform((current) => ({
      ...current,
      x: currentDrag.originX + event.clientX - currentDrag.startX,
      y: currentDrag.originY + event.clientY - currentDrag.startY,
    }));
  }, []);

  const onPointerUp = useCallback(() => {
    drag.current = null;
  }, []);

  return (
    <Dialog onOpenChange={onOpenChange} open={open}>
      <div
        className={cn("aui-flow-expand group/flow relative", className)}
        data-slot="flow-expand"
        {...props}
      >
        {children}
        <DialogTrigger
          render={
            <Button
              aria-label="Expand diagram"
              className={cn(
                flowControlButtonClass,
                "aui-flow-expand-trigger absolute end-2 top-2 opacity-0 focus-visible:opacity-100 group-hover/flow:opacity-100"
              )}
              size="icon-sm"
              title="Expand diagram"
              type="button"
              variant="ghost"
            >
              <Maximize2 className="size-3.5" />
            </Button>
          }
        />
        <DialogContent
          className="aui-flow-dialog-content fixed inset-0 start-0 top-0 z-50 max-w-none translate-x-0 translate-y-0 rounded-none border-0 bg-background p-0 shadow-none sm:max-w-none"
          showCloseButton={false}
        >
          <DialogTitle className="aui-sr-only sr-only">Diagram</DialogTitle>
          <DialogDescription className="aui-sr-only sr-only">
            Expanded diagram viewer
          </DialogDescription>
          <div
            className="aui-flow-expand-viewport h-full w-full cursor-grab touch-none overflow-hidden active:cursor-grabbing"
            data-slot="flow-expand-viewport"
            onPointerCancel={onPointerUp}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onWheel={onWheel}
            ref={viewportRef}
          >
            <div
              className="aui-flow-expand-content flex h-full w-full items-center justify-center"
              data-slot="flow-expand-content"
              style={{
                transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.scale})`,
                transformOrigin: "0 0",
              }}
            >
              {children}
            </div>
          </div>
          <div
            className="aui-flow-expand-controls absolute end-4 top-4 flex items-center gap-1"
            data-slot="flow-expand-controls"
          >
            <Button
              aria-label="Zoom in"
              className={flowControlButtonClass}
              onClick={() => zoomBy(1.25)}
              size="icon-sm"
              title="Zoom in"
              type="button"
              variant="ghost"
            >
              <Plus className="size-4" />
            </Button>
            <Button
              aria-label="Zoom out"
              className={flowControlButtonClass}
              onClick={() => zoomBy(0.8)}
              size="icon-sm"
              title="Zoom out"
              type="button"
              variant="ghost"
            >
              <Minus className="size-4" />
            </Button>
            <Button
              aria-label="Reset zoom"
              className={flowControlButtonClass}
              onClick={() => setTransform({ x: 0, y: 0, scale: 1 })}
              size="icon-sm"
              title="Reset zoom"
              type="button"
              variant="ghost"
            >
              <RotateCcw className="size-4" />
            </Button>
            <DialogClose
              render={
                <Button
                  aria-label="Close diagram"
                  className={flowControlButtonClass}
                  size="icon-sm"
                  title="Close diagram"
                  type="button"
                  variant="ghost"
                >
                  <X className="size-4" />
                </Button>
              }
            />
          </div>
        </DialogContent>
      </div>
    </Dialog>
  );
}
