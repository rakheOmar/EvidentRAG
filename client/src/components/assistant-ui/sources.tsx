"use client";

import type { SourceMessagePartComponent } from "@assistant-ui/react";
import { FileTextIcon } from "lucide-react";
import { type ComponentProps, memo, useState } from "react";
import { cn } from "@/lib/utils";
import { Badge, type BadgeProps, badgeVariants } from "./badge";

const extractDomain = (url: string): string => {
	try {
		return new URL(url).hostname.replace(/^www\./, "");
	} catch {
		return url;
	}
};

const defaultFaviconUrl = (domain: string) =>
	`https://icons.duckduckgo.com/ip3/${domain}.ico`;

function SourceIcon({
	url,
	className,
	faviconUrl = defaultFaviconUrl,
	...props
}: ComponentProps<"span"> & {
	url: string;
	faviconUrl?: (domain: string) => string;
}) {
	const domain = extractDomain(url);
	const src = faviconUrl(domain);
	const [errorSrc, setErrorSrc] = useState<string | undefined>(undefined);
	const hasError = errorSrc === src;

	if (hasError) {
		return (
			<span
				className={cn(
					"flex size-3 shrink-0 items-center justify-center rounded-sm bg-muted font-medium text-[10px]",
					className,
				)}
				data-slot="source-icon-fallback"
				{...props}
			>
				{domain.charAt(0).toUpperCase() || "?"}
			</span>
		);
	}

	return (
		<img
			alt=""
			className={cn("size-3 shrink-0 rounded-sm", className)}
			data-slot="source-icon"
			onError={() => setErrorSrc(src)}
			src={src}
			{...(props as ComponentProps<"img">)}
		/>
	);
}

function SourceTitle({ className, ...props }: ComponentProps<"span">) {
	return (
		<span
			className={cn("max-w-37.5 truncate", className)}
			data-slot="source-title"
			{...props}
		/>
	);
}

function DocumentSourceIcon({ className, ...props }: ComponentProps<"span">) {
	return (
		<span
			className={cn(
				"flex size-3 shrink-0 items-center justify-center text-muted-foreground",
				className,
			)}
			data-slot="source-document-icon"
			{...props}
		>
			<FileTextIcon className="size-3" />
		</span>
	);
}

export type SourceProps = Omit<BadgeProps, "asChild"> &
	ComponentProps<"a"> & {
		asChild?: boolean;
	};

function Source({
	className,
	variant,
	size,
	asChild = false,
	target = "_blank",
	rel = "noopener noreferrer",
	...props
}: SourceProps) {
	return (
		<Badge
			asChild
			className={cn(
				"cursor-pointer outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50",
				className,
			)}
			size={size}
			variant={variant}
		>
			<a
				data-slot="source"
				rel={rel}
				target={target}
				{...(props as ComponentProps<"a">)}
			/>
		</Badge>
	);
}

const SourcesImpl: SourceMessagePartComponent = (part) => {
	if (part.sourceType === "url" && part.url) {
		const domain = extractDomain(part.url);
		const displayTitle = part.title || domain;

		return (
			<Source href={part.url}>
				<SourceIcon url={part.url} />
				<SourceTitle>{displayTitle}</SourceTitle>
			</Source>
		);
	}

	if (part.sourceType === "document") {
		return (
			<Badge
				className="outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
				variant="secondary"
			>
				<span className="inline-flex items-center gap-1.5" data-slot="source">
					<DocumentSourceIcon />
					<SourceTitle>{part.title}</SourceTitle>
				</span>
			</Badge>
		);
	}

	return null;
};

const Sources = memo(SourcesImpl) as unknown as SourceMessagePartComponent & {
	Root: typeof Source;
	Icon: typeof SourceIcon;
	Title: typeof SourceTitle;
};

Sources.displayName = "Sources";
Sources.Root = Source;
Sources.Icon = SourceIcon;
Sources.Title = SourceTitle;

export {
	badgeVariants as sourceVariants,
	Source,
	SourceIcon,
	Sources,
	SourceTitle,
};
