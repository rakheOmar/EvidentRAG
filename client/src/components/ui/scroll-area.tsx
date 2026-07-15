import { ScrollArea as ScrollAreaPrimitive } from "@base-ui/react/scroll-area";
import type * as React from "react";

import { cn } from "@/lib/utils";

type ScrollAreaOrientation = "both" | "horizontal" | "vertical";

interface ScrollAreaProps extends ScrollAreaPrimitive.Root.Props {
	orientation?: ScrollAreaOrientation;
	scrollFade?: boolean;
	viewportClassName?: string;
	viewportProps?: ScrollAreaPrimitive.Viewport.Props;
	viewportRef?: React.Ref<HTMLDivElement>;
}

function ScrollArea({
	className,
	children,
	orientation = "vertical",
	scrollFade = false,
	viewportClassName,
	viewportProps,
	viewportRef,
	...rootProps
}: ScrollAreaProps) {
	return (
		<ScrollAreaPrimitive.Root
			className={cn("relative", className)}
			data-slot="scroll-area"
			{...rootProps}
		>
			<ScrollAreaPrimitive.Viewport
				className={cn(
					"size-full rounded-[inherit] outline-none transition-[color,box-shadow] focus-visible:outline-1 focus-visible:ring-[3px] focus-visible:ring-ring/50",
					scrollFade &&
						"data-[overflow-y-end]:[mask-image:linear-gradient(to_bottom,black_calc(100%-1.5rem),transparent)]",
					viewportClassName,
				)}
				data-slot="scroll-area-viewport"
				ref={viewportRef}
				{...viewportProps}
			>
				{children}
			</ScrollAreaPrimitive.Viewport>
			{orientation !== "horizontal" ? (
				<ScrollBar orientation="vertical" />
			) : null}
			{orientation !== "vertical" ? (
				<ScrollBar orientation="horizontal" />
			) : null}
			<ScrollAreaPrimitive.Corner />
		</ScrollAreaPrimitive.Root>
	);
}

function ScrollBar({
	className,
	orientation = "vertical",
	...props
}: ScrollAreaPrimitive.Scrollbar.Props) {
	return (
		<ScrollAreaPrimitive.Scrollbar
			className={cn(
				"flex touch-none select-none p-px transition-colors data-horizontal:h-2.5 data-vertical:h-full data-vertical:w-2.5 data-horizontal:flex-col data-horizontal:border-t data-horizontal:border-t-transparent data-vertical:border-l data-vertical:border-l-transparent",
				className,
			)}
			data-orientation={orientation}
			data-slot="scroll-area-scrollbar"
			orientation={orientation}
			{...props}
		>
			<ScrollAreaPrimitive.Thumb
				className="relative flex-1 rounded-full bg-border"
				data-slot="scroll-area-thumb"
			/>
		</ScrollAreaPrimitive.Scrollbar>
	);
}

export { ScrollArea, ScrollBar };
