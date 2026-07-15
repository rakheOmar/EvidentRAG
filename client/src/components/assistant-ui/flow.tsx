import { cva, type VariantProps } from "class-variance-authority";
import type { ComponentProps, ReactNode } from "react";

import { FlowCanvas } from "@/components/assistant-ui/flow-canvas";
import { FlowExpand } from "@/components/assistant-ui/flow-expand";
import { cn } from "@/lib/utils";

export type FlowRootProps = ComponentProps<"div"> & {
	llm?: string;
};

function FlowRoot({ className, children, llm: _llm, ...props }: FlowRootProps) {
	return (
		<div
			className={cn(
				"aui-flow-root not-prose my-6 overflow-x-auto overflow-y-hidden",
				className,
			)}
			data-slot="flow-root"
			{...props}
		>
			<FlowExpand>
				<div
					className="aui-flow-content mx-auto w-fit py-3"
					data-slot="flow-content"
				>
					{children}
				</div>
			</FlowExpand>
		</div>
	);
}

export type FlowRowProps = ComponentProps<"div">;

function FlowRow({ className, ...props }: FlowRowProps) {
	return (
		<div
			className={cn(
				"aui-flow-row flex items-center justify-center gap-3",
				className,
			)}
			data-slot="flow-row"
			{...props}
		/>
	);
}

export type FlowColumnProps = ComponentProps<"div">;

function FlowColumn({ className, ...props }: FlowColumnProps) {
	return (
		<div
			className={cn(
				"aui-flow-column flex flex-col items-center gap-3",
				className,
			)}
			data-slot="flow-column"
			{...props}
		/>
	);
}

export type FlowGroupProps = ComponentProps<"div"> & {
	flowId?: string;
};

function FlowGroup({ className, flowId, ...props }: FlowGroupProps) {
	return (
		<div
			className={cn(
				"aui-flow-group relative rounded-xl border border-border border-dashed p-4",
				className,
			)}
			data-flow-id={flowId}
			data-slot="flow-group"
			{...props}
		/>
	);
}

export type FlowGroupLabelProps = ComponentProps<"span">;

function FlowGroupLabel({ className, ...props }: FlowGroupLabelProps) {
	return (
		<span
			className={cn(
				"aui-flow-group-label absolute -top-2 left-3 bg-background px-1.5 font-medium text-[10px] text-muted-foreground uppercase tracking-widest",
				className,
			)}
			data-slot="flow-group-label"
			{...props}
		/>
	);
}

const flowNodeVariants = cva(
	"aui-flow-node relative inline-flex items-center justify-center whitespace-nowrap text-sm",
	{
		variants: {
			variant: {
				box: "rounded-md border border-border bg-card px-3.5 py-1.5 text-card-foreground",
				decision: "px-8 py-4 text-card-foreground",
			},
			tone: {
				default: "",
				pink: "border-pink-500/60 bg-pink-500/10",
				blue: "border-blue-500/60 bg-blue-500/10",
				red: "border-red-500/60 bg-red-500/10",
				green: "border-green-500/60 bg-green-500/10",
			},
		},
		defaultVariants: {
			variant: "box",
			tone: "default",
		},
	},
);

export type FlowNodeProps = ComponentProps<"span"> &
	VariantProps<typeof flowNodeVariants> & {
		flowId?: string;
	};

function FlowNode({
	className,
	flowId,
	variant = "box",
	tone,
	children,
	...props
}: FlowNodeProps) {
	return (
		<span
			className={cn(flowNodeVariants({ variant, tone }), className)}
			data-flow-id={flowId}
			data-slot="flow-node"
			data-tone={tone ?? "default"}
			data-variant={variant}
			{...props}
		>
			{variant === "decision" && (
				<svg
					aria-hidden
					className="aui-flow-node-decision-shape absolute inset-0 h-full w-full"
					data-slot="flow-node-decision-shape"
					preserveAspectRatio="none"
					viewBox="0 0 100 100"
				>
					<polygon
						className="fill-card stroke-border"
						points="50,1 99,50 50,99 1,50"
						strokeWidth={1}
						vectorEffect="non-scaling-stroke"
					/>
				</svg>
			)}
			<span className="relative" data-slot="flow-node-content">
				{children}
			</span>
		</span>
	);
}

function FlowLLMRoot({ llm }: { llm?: string; children?: ReactNode }) {
	if (!llm) {
		return null;
	}
	return (
		<pre>
			<code className="language-mermaid">{llm}</code>
		</pre>
	);
}

function FlowLLMPassthrough({ children }: { children?: ReactNode }) {
	return <>{children}</>;
}

function FlowLLMArrow() {
	return null;
}

function FlowCanvasRoot(props: ComponentProps<typeof FlowCanvas>) {
	return <FlowCanvas {...props} />;
}

export type FlowArrowProps = ComponentProps<"div"> & {
	label?: ReactNode;
	reverseLabel?: ReactNode;
	direction?: "right" | "down";
	length?: number;
};

function FlowArrow({
	className,
	label,
	reverseLabel,
	direction = "right",
	length = 88,
	...props
}: FlowArrowProps) {
	if (direction === "down") {
		return (
			<div
				className={cn(
					"aui-flow-arrow relative flex justify-center text-muted-foreground/70",
					className,
				)}
				data-direction={direction}
				data-slot="flow-arrow"
				{...props}
			>
				<svg aria-hidden data-slot="flow-arrow-svg" height={length} width={10}>
					<line
						stroke="currentColor"
						strokeWidth={1.5}
						x1={5}
						x2={5}
						y1={0}
						y2={length - 6}
					/>
					<path
						d={`M 1.5 ${length - 7} L 5 ${length} L 8.5 ${length - 7} Z`}
						fill="currentColor"
					/>
				</svg>
				{label && (
					<span
						className="aui-flow-arrow-label absolute top-1/2 left-1/2 ml-2.5 -translate-y-1/2 whitespace-nowrap text-xs"
						data-slot="flow-arrow-label"
					>
						{label}
					</span>
				)}
			</div>
		);
	}

	return (
		<div
			className={cn(
				"aui-flow-arrow flex flex-col items-center gap-1 text-muted-foreground/70",
				className,
			)}
			data-direction={direction}
			data-slot="flow-arrow"
			{...props}
		>
			{label && (
				<span
					className="aui-flow-arrow-label whitespace-nowrap text-xs"
					data-slot="flow-arrow-label"
				>
					{label}
				</span>
			)}
			<svg aria-hidden data-slot="flow-arrow-svg" height={10} width={length}>
				<line
					stroke="currentColor"
					strokeWidth={1.5}
					x1={0}
					x2={length - 6}
					y1={5}
					y2={5}
				/>
				<path
					d={`M ${length - 7} 1.5 L ${length} 5 L ${length - 7} 8.5 Z`}
					fill="currentColor"
				/>
			</svg>
			{reverseLabel && (
				<>
					<svg
						aria-hidden
						data-slot="flow-arrow-reverse-svg"
						height={10}
						width={length}
					>
						<line
							stroke="currentColor"
							strokeWidth={1.5}
							x1={6}
							x2={length}
							y1={5}
							y2={5}
						/>
						<path d="M 7 1.5 L 0 5 L 7 8.5 Z" fill="currentColor" />
					</svg>
					<span
						className="aui-flow-arrow-label whitespace-nowrap text-xs"
						data-slot="flow-arrow-reverse-label"
					>
						{reverseLabel}
					</span>
				</>
			)}
		</div>
	);
}

export const Flow = Object.assign(FlowRoot, {
	Arrow: FlowArrow,
	Canvas: FlowCanvasRoot,
	Column: FlowColumn,
	Group: FlowGroup,
	GroupLabel: FlowGroupLabel,
	Node: FlowNode,
	Root: FlowRoot,
	Row: FlowRow,
});

export const FlowLLM = Object.assign(FlowLLMRoot, {
	Arrow: FlowLLMArrow,
	Canvas: FlowLLMPassthrough,
	Column: FlowLLMPassthrough,
	Group: FlowLLMPassthrough,
	GroupLabel: FlowLLMPassthrough,
	Node: FlowLLMPassthrough,
	Root: FlowLLMRoot,
	Row: FlowLLMPassthrough,
});

export {
	FlowArrow,
	FlowCanvasRoot as FlowCanvas,
	FlowColumn,
	FlowGroup,
	FlowGroupLabel,
	FlowNode,
	FlowRoot,
	FlowRow,
	flowNodeVariants,
};
