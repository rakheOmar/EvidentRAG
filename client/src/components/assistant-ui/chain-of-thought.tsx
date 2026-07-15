"use client";

import { ArrowDown01Icon, Brain02Icon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { useControllableState } from "@radix-ui/react-use-controllable-state";
import type { ComponentProps, CSSProperties, ReactNode } from "react";
import { createContext, memo, useContext, useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import {
	Collapsible,
	CollapsibleContent,
	CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";

interface ChainOfThoughtContextValue {
	isOpen: boolean;
	setIsOpen: (open: boolean) => void;
}

const ChainOfThoughtContext = createContext<ChainOfThoughtContextValue | null>(
	null,
);

const useChainOfThought = () => {
	const context = useContext(ChainOfThoughtContext);
	if (!context) {
		throw new Error(
			"ChainOfThought components must be used within ChainOfThought",
		);
	}
	return context;
};

export type ChainOfThoughtProps = ComponentProps<"div"> & {
	open?: boolean;
	defaultOpen?: boolean;
	onOpenChange?: (open: boolean) => void;
};

export const ChainOfThought = memo(
	({
		className,
		open,
		defaultOpen = false,
		onOpenChange,
		children,
		...props
	}: ChainOfThoughtProps) => {
		const [isOpen, setIsOpen] = useControllableState({
			defaultProp: defaultOpen,
			onChange: onOpenChange,
			prop: open,
		});

		const chainOfThoughtContext = useMemo(
			() => ({ isOpen, setIsOpen }),
			[isOpen, setIsOpen],
		);

		return (
			<ChainOfThoughtContext.Provider value={chainOfThoughtContext}>
				<div className={cn("not-prose w-full space-y-4", className)} {...props}>
					{children}
				</div>
			</ChainOfThoughtContext.Provider>
		);
	},
);

export type ChainOfThoughtHeaderProps = ComponentProps<
	typeof CollapsibleTrigger
> & {
	shimmer?: boolean;
};

export const ChainOfThoughtHeader = memo(
	({ className, shimmer, children, ...props }: ChainOfThoughtHeaderProps) => {
		const { isOpen, setIsOpen } = useChainOfThought();

		return (
			<Collapsible onOpenChange={setIsOpen} open={isOpen}>
				<CollapsibleTrigger
					className={cn(
						"flex w-full items-center gap-3 rounded-2xl px-2 py-1.5 text-muted-foreground text-sm transition-[background-color,color] duration-150 hover:bg-muted/30 hover:text-foreground",
						className,
					)}
					{...props}
				>
					<div className="flex size-8 items-center justify-center rounded-xl bg-muted/30 text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
						<HugeiconsIcon
							className="size-4"
							icon={Brain02Icon}
							strokeWidth={1.8}
						/>
					</div>
					<span
						className={cn(
							"flex-1 text-left font-medium text-sm leading-none",
							shimmer && "shimmer",
						)}
					>
						{children ?? "Chain of Thought"}
					</span>
					<HugeiconsIcon
						className={cn(
							"size-4 transition-transform duration-200",
							isOpen ? "rotate-180" : "rotate-0",
						)}
						icon={ArrowDown01Icon}
						strokeWidth={1.8}
					/>
				</CollapsibleTrigger>
			</Collapsible>
		);
	},
);

export type ChainOfThoughtStepProps = ComponentProps<"div"> & {
	icon?: ReactNode;
	index?: number;
	label: ReactNode;
	description?: ReactNode;
	status?: "complete" | "active" | "pending";
};

const stepStatusStyles = {
	active: "text-foreground",
	complete: "text-foreground/90",
	pending: "text-muted-foreground/50",
};

export const ChainOfThoughtStep = memo(
	({
		className,
		icon,
		index = 0,
		label,
		description,
		status = "complete",
		children,
		style,
		...props
	}: ChainOfThoughtStepProps) => {
		const stepStyle: CSSProperties = {
			animationDelay: `${index * 70}ms`,
			...style,
		};

		return (
			<div
				className={cn(
					"flex gap-2 text-xs",
					stepStatusStyles[status],
					"fade-in-0 slide-in-from-top-2 animate-in duration-300",
					className,
				)}
				style={stepStyle}
				{...props}
			>
				<div className="relative flex flex-col items-center">
					<div className="relative z-10 flex size-5 items-center justify-center rounded-full bg-background text-muted-foreground">
						{icon ?? (
							<div
								className="size-1.5 rounded-full bg-current/60"
								aria-hidden
							/>
						)}
					</div>
					<div className="absolute inset-y-0 -bottom-3 left-1/2 w-px origin-top bg-border/40 animate-line-grow duration-300 ease-out" />
				</div>
				<div className="flex-1 space-y-1 overflow-hidden">
					<div className="text-pretty leading-5">{label}</div>
					{description && (
						<div className="text-muted-foreground/75 text-xs leading-5">
							{description}
						</div>
					)}
					{children}
				</div>
			</div>
		);
	},
);

export type ChainOfThoughtSearchResultsProps = ComponentProps<"div">;

export const ChainOfThoughtSearchResults = memo(
	({ className, ...props }: ChainOfThoughtSearchResultsProps) => (
		<div
			className={cn("flex flex-wrap items-center gap-2", className)}
			{...props}
		/>
	),
);

export type ChainOfThoughtSearchResultProps = ComponentProps<typeof Badge>;

export const ChainOfThoughtSearchResult = memo(
	({ className, children, ...props }: ChainOfThoughtSearchResultProps) => (
		<Badge
			className={cn("gap-1 px-2 py-0.5 font-normal text-xs", className)}
			variant="secondary"
			{...props}
		>
			{children}
		</Badge>
	),
);

export type ChainOfThoughtContentProps = ComponentProps<
	typeof CollapsibleContent
>;

export const ChainOfThoughtContent = memo(
	({ className, children, ...props }: ChainOfThoughtContentProps) => {
		const { isOpen } = useChainOfThought();

		return (
			<Collapsible open={isOpen}>
				<CollapsibleContent
					className={cn(
						"mt-2 space-y-2.5 rounded-[1.4rem] bg-muted/[0.14] p-2.5",
						"data-[state=closed]:fade-out-0 data-[state=closed]:slide-out-to-top-2 data-[state=open]:slide-in-from-top-2 text-popover-foreground outline-none data-[state=closed]:animate-out data-[state=open]:animate-in duration-200",
						className,
					)}
					{...props}
				>
					{children}
				</CollapsibleContent>
			</Collapsible>
		);
	},
);

export type ChainOfThoughtImageProps = ComponentProps<"div"> & {
	caption?: string;
};

export const ChainOfThoughtImage = memo(
	({ className, children, caption, ...props }: ChainOfThoughtImageProps) => (
		<div className={cn("mt-2 space-y-2", className)} {...props}>
			<div className="relative flex max-h-88 items-center justify-center overflow-hidden rounded-lg bg-muted p-3">
				{children}
			</div>
			{caption && <p className="text-muted-foreground text-xs">{caption}</p>}
		</div>
	),
);

ChainOfThought.displayName = "ChainOfThought";
ChainOfThoughtHeader.displayName = "ChainOfThoughtHeader";
ChainOfThoughtStep.displayName = "ChainOfThoughtStep";
ChainOfThoughtSearchResults.displayName = "ChainOfThoughtSearchResults";
ChainOfThoughtSearchResult.displayName = "ChainOfThoughtSearchResult";
ChainOfThoughtContent.displayName = "ChainOfThoughtContent";
ChainOfThoughtImage.displayName = "ChainOfThoughtImage";
