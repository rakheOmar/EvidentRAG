"use client";

import { XIcon } from "lucide-react";
import { type FC, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useEvidencePanel } from "@/components/chat/evidence-context";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useIsMobile } from "@/hooks/use-mobile";
import { cn } from "@/lib/utils";

export interface EvidencePanelData {
  content: string;
  context_header: string | null;
  document_title: string | null;
  document_slug: string | null;
  page: number | null;
  id: string;
}

interface EvidenceSidepanelProps {
  evidence: EvidencePanelData[] | null;
  activeEvidenceId: string | null;
  open: boolean;
  onClose: () => void;
}

const EvidenceSidepanel: FC<EvidenceSidepanelProps> = ({
  evidence,
  activeEvidenceId,
  open,
  onClose,
}) => {
  const isMobile = useIsMobile();
  const { selectEvidence } = useEvidencePanel();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const prevActiveRef = useRef(activeEvidenceId);

  useEffect(() => {
    if (activeEvidenceId) {
      setDismissed(false);
    }
  }, [activeEvidenceId]);

  useEffect(() => {
    if (activeEvidenceId && activeEvidenceId !== prevActiveRef.current) {
      setMobileOpen(true);
    }
    prevActiveRef.current = activeEvidenceId;
  }, [activeEvidenceId]);

  const handleClose = useCallback(() => {
    setDismissed(true);
    setMobileOpen(false);
    selectEvidence([]);
    onClose();
  }, [selectEvidence, onClose]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    },
    [onClose],
  );

  const accordionValue = useMemo(
    () => (activeEvidenceId ? [activeEvidenceId] : []),
    [activeEvidenceId]
  );

  const accordionContent = (
    <Accordion
      className="overflow-hidden"
      onValueChange={(value) => {
        const id = Array.isArray(value) ? value[0] : undefined;
        if (!id || id === activeEvidenceId) {
          selectEvidence([]);
        } else {
          selectEvidence([id]);
        }
      }}
      value={accordionValue}
    >
      {evidence?.map((item) => (
        <AccordionItem className="min-w-0" key={item.id} value={item.id}>
          <AccordionTrigger className="min-w-0 px-4 py-2.5">
            <div className="flex min-w-0 items-center gap-2">
              {item.document_title && (
                <span className="truncate text-sm font-medium">
                  {item.document_title}
                </span>
              )}
              {item.page != null && (
                <span className="shrink-0 text-xs text-sidebar-foreground/50">
                  p. {item.page}
                </span>
              )}
            </div>
          </AccordionTrigger>
          <AccordionContent>
            <div className="min-w-0 space-y-1.5 px-4 pb-3">
              {item.context_header && (
                <p className="text-[11px] font-medium uppercase tracking-wider text-sidebar-foreground/40">
                  {item.context_header}
                </p>
              )}
              <p className="wrap-break-word text-xs leading-relaxed text-foreground/90">
                {item.content}
              </p>
            </div>
          </AccordionContent>
        </AccordionItem>
      ))}
    </Accordion>
  );

  if (isMobile) {
    return (
      <Drawer
        onOpenChange={(nextOpen) => {
          if (!nextOpen) handleClose();
        }}
        open={mobileOpen}
      >
        <DrawerContent className="bg-sidebar text-sidebar-foreground">
          <DrawerHeader className="border-b border-sidebar-border pb-2">
            <DrawerTitle className="text-sidebar-foreground">
              Evidence
            </DrawerTitle>
          </DrawerHeader>
          <ScrollArea className="flex-1">{accordionContent}</ScrollArea>
        </DrawerContent>
      </Drawer>
    );
  }

  return (
    <section
      className={cn(
        "flex w-full flex-col overflow-hidden rounded-xl border border-sidebar-border bg-sidebar text-sidebar-foreground shadow-lg transition-all duration-300 ease-in-out",
        open && !dismissed
          ? "translate-x-0 opacity-100"
          : "translate-x-8 opacity-0 pointer-events-none",
      )}
      onKeyDown={handleKeyDown}
      aria-label="Evidence details"
      aria-hidden={!open || dismissed}
    >
      <div className="flex shrink-0 items-center justify-between border-b border-sidebar-border px-4 py-3">
        <h2 className="font-medium text-sm">Evidence</h2>
        <Button
          aria-label="Close evidence panel"
          className="size-6"
          onClick={handleClose}
          size="icon"
          variant="ghost"
        >
          <XIcon className="size-3.5" />
        </Button>
      </div>
      <ScrollArea className="flex-1">{accordionContent}</ScrollArea>
    </section>
  );
};

export { EvidenceSidepanel };
