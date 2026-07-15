"use client";

import { XIcon } from "lucide-react";
import { type FC, useCallback, useMemo } from "react";
import { useEvidencePanel } from "@/components/chat/evidence-context";
import {
	Accordion,
	AccordionContent,
	AccordionItem,
	AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
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
	document_slug: string | null;
	document_title: string | null;
	erm_multiplier: number | null;
	erm_state: "boost" | "penalty" | null;
	id: string;
	page: number | null;
}

interface EvidenceSidepanelProps {
	activeEvidenceId: string | null;
	evidence: EvidencePanelData[] | null;
	onClose: () => void;
	open: boolean;
}

const EvidenceAccordionItem: FC<{ item: EvidencePanelData }> = ({ item }) => (
	<AccordionItem className="min-w-0" value={item.id}>
		<AccordionTrigger className="min-w-0 px-4 py-2.5">
			<div className="flex min-w-0 items-center gap-2">
				{item.document_title ? (
					<span className="truncate font-medium text-sm">
						{item.document_title}
					</span>
				) : null}
				{typeof item.page === "number" && Number.isFinite(item.page) ? (
					<span className="shrink-0 text-sidebar-foreground/50 text-xs">
						p. {item.page}
					</span>
				) : null}
			</div>
		</AccordionTrigger>
		<AccordionContent>
			<div className="min-w-0 space-y-1.5 px-4 pb-3">
				{item.erm_state ? (
					<div className="flex items-center gap-2">
						<Badge
							className={cn(
								item.erm_state === "boost"
									? "bg-emerald-500/15 text-emerald-700"
									: "bg-rose-500/15 text-rose-700",
							)}
							variant="secondary"
						>
							{item.erm_state === "boost" ? "ERM boost" : "ERM penalty"}
						</Badge>
						{item.erm_multiplier === null ? null : (
							<span className="text-sidebar-foreground/50 text-xs tabular-nums">
								x{item.erm_multiplier.toFixed(2)}
							</span>
						)}
					</div>
				) : null}
				{item.context_header ? (
					<p className="font-medium text-[11px] text-sidebar-foreground/40 uppercase tracking-wider">
						{item.context_header}
					</p>
				) : null}
				<p className="wrap-break-word text-foreground/90 text-wrap-pretty text-xs leading-relaxed">
					{item.content}
				</p>
			</div>
		</AccordionContent>
	</AccordionItem>
);

const EvidenceSidepanel: FC<EvidenceSidepanelProps> = ({
	evidence,
	activeEvidenceId,
	open,
	onClose,
}) => {
	const isMobile = useIsMobile();
	const { clearEvidence, selectedMessageId, selectEvidence } =
		useEvidencePanel();

	const handleClose = useCallback(() => {
		clearEvidence();
		onClose();
	}, [clearEvidence, onClose]);

	const handleKeyDown = useCallback(
		(e: React.KeyboardEvent) => {
			if (e.key === "Escape") {
				onClose();
			}
		},
		[onClose],
	);

	const handleOpenChange = useCallback<
		NonNullable<React.ComponentProps<typeof Drawer>["onOpenChange"]>
	>(
		(nextOpen) => {
			if (!nextOpen) {
				handleClose();
			}
		},
		[handleClose],
	);

	const handleValueChange = useCallback<
		NonNullable<React.ComponentProps<typeof Accordion>["onValueChange"]>
	>(
		(value) => {
			const id = Array.isArray(value) ? value[0] : undefined;
			if (!id || id === activeEvidenceId) {
				clearEvidence();
				return;
			}
			if (selectedMessageId) {
				selectEvidence(selectedMessageId, [id]);
			} else {
				clearEvidence();
			}
		},
		[activeEvidenceId, clearEvidence, selectedMessageId, selectEvidence],
	);

	const accordionValue = useMemo(
		() => (activeEvidenceId ? [activeEvidenceId] : []),
		[activeEvidenceId],
	);

	const accordionContent = useMemo(
		() => (
			<Accordion
				className="overflow-hidden"
				onValueChange={handleValueChange}
				value={accordionValue}
			>
				{evidence?.map((item) => (
					<EvidenceAccordionItem item={item} key={item.id} />
				))}
			</Accordion>
		),
		[accordionValue, evidence, handleValueChange],
	);

	if (isMobile) {
		return (
			<Drawer onOpenChange={handleOpenChange} open={open}>
				<DrawerContent className="bg-sidebar text-sidebar-foreground">
					<DrawerHeader className="border-sidebar-border border-b pb-2">
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
			aria-hidden={!open}
			aria-label="Evidence details"
			className={cn(
				"flex w-full flex-col overflow-hidden rounded-xl border border-sidebar-border bg-sidebar text-sidebar-foreground shadow-lg transition-[transform,opacity] duration-300 ease-in-out",
				open
					? "translate-x-0 opacity-100"
					: "pointer-events-none translate-x-8 opacity-0",
			)}
			onKeyDown={handleKeyDown}
		>
			<div className="flex shrink-0 items-center justify-between border-sidebar-border border-b px-4 py-3">
				<h2 className="font-medium text-sm">Evidence</h2>
				<Button
					aria-label="Close evidence panel"
					className="relative size-6 before:absolute before:-inset-2 before:content-[''] active:scale-96"
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
