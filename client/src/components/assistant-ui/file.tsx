"use client";

import type { FileMessagePartComponent } from "@assistant-ui/react";
import { cva, type VariantProps } from "class-variance-authority";
import {
	BracesIcon,
	DownloadIcon,
	FileIcon,
	FileTextIcon,
	ImageIcon,
	MusicIcon,
	VideoIcon,
} from "lucide-react";
import { type FC, memo } from "react";
import { cn } from "@/lib/utils";

const fileVariants = cva(
	"aui-file-root inline-flex items-center gap-3 rounded-lg transition-colors",
	{
		variants: {
			variant: {
				outline: "border border-border hover:bg-muted/50",
				ghost: "hover:bg-muted/50",
				muted: "bg-muted/50 hover:bg-muted/70",
			},
			size: {
				sm: "px-2.5 py-1.5 text-xs",
				default: "px-3 py-2 text-sm",
				lg: "px-4 py-3 text-base",
			},
		},
		defaultVariants: {
			variant: "outline",
			size: "default",
		},
	},
);

function getMimeTypeIcon(mimeType: string): FC<{ className?: string }> {
	if (mimeType.startsWith("image/")) {
		return ImageIcon;
	}
	if (mimeType === "application/pdf") {
		return FileTextIcon;
	}
	if (mimeType === "application/json") {
		return BracesIcon;
	}
	if (mimeType.startsWith("text/")) {
		return FileTextIcon;
	}
	if (mimeType.startsWith("audio/")) {
		return MusicIcon;
	}
	if (mimeType.startsWith("video/")) {
		return VideoIcon;
	}
	return FileIcon;
}

function getBase64Size(base64: string): number {
	const commaIndex = base64.indexOf(",");
	const base64Data = commaIndex >= 0 ? base64.slice(commaIndex + 1) : base64;
	const padding = (base64Data.match(/=/g) || []).length;
	return Math.floor((base64Data.length * 3) / 4) - padding;
}

function formatFileSize(bytes: number): string {
	if (bytes < 1024) {
		return `${bytes} B`;
	}
	if (bytes < 1024 * 1024) {
		return `${(bytes / 1024).toFixed(1)} KB`;
	}
	return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export type FileRootProps = React.ComponentProps<"div"> &
	VariantProps<typeof fileVariants>;

function FileRoot({
	className,
	variant,
	size,
	children,
	...props
}: FileRootProps) {
	return (
		<div
			className={cn(fileVariants({ variant, size, className }))}
			data-size={size}
			data-slot="file-root"
			data-variant={variant}
			{...props}
		>
			{children}
		</div>
	);
}

type FileIconDisplayProps = React.ComponentProps<"span"> & {
	mimeType?: string;
};

function FileIconDisplay({
	mimeType,
	className,
	children,
	...props
}: FileIconDisplayProps) {
	const IconComponent = mimeType ? getMimeTypeIcon(mimeType) : FileIcon;

	return (
		<span
			className={cn("shrink-0 text-muted-foreground", className)}
			data-slot="file-icon"
			{...props}
		>
			{children ?? <IconComponent className="size-5" />}
		</span>
	);
}

function FileName({
	className,
	children,
	...props
}: React.ComponentProps<"span">) {
	return (
		<span
			className={cn("min-w-0 flex-1 truncate font-medium", className)}
			data-slot="file-name"
			{...props}
		>
			{children || "Unnamed file"}
		</span>
	);
}

type FileSizeProps = React.ComponentProps<"span"> & {
	bytes: number;
};

function FileSize({ bytes, className, ...props }: FileSizeProps) {
	return (
		<span
			className={cn("shrink-0 text-muted-foreground", className)}
			data-slot="file-size"
			{...props}
		>
			{formatFileSize(bytes)}
		</span>
	);
}

type FileDownloadProps = Omit<React.ComponentProps<"a">, "href"> & {
	data: string;
	mimeType: string;
	filename?: string;
};

function FileDownload({
	data,
	mimeType,
	filename,
	className,
	children,
	...props
}: FileDownloadProps) {
	const href = data.startsWith("data:")
		? data
		: `data:${mimeType};base64,${data}`;

	return (
		<a
			className={cn(
				"shrink-0 rounded-md p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground",
				className,
			)}
			data-slot="file-download"
			download={filename || "download"}
			href={href}
			{...props}
		>
			{children || <DownloadIcon className="size-4" />}
		</a>
	);
}

const FileImpl: FileMessagePartComponent = ({ filename, data, mimeType }) => {
	const bytes = getBase64Size(data);

	return (
		<FileRoot>
			<FileIconDisplay mimeType={mimeType} />
			<div className="flex min-w-0 flex-1 flex-col gap-0.5">
				<FileName>{filename}</FileName>
				<FileSize bytes={bytes} className="text-xs" />
			</div>
			<FileDownload
				data={data}
				mimeType={mimeType}
				{...(filename !== undefined && { filename })}
			/>
		</FileRoot>
	);
};

const File = memo(FileImpl) as unknown as FileMessagePartComponent & {
	Root: typeof FileRoot;
	Icon: typeof FileIconDisplay;
	Name: typeof FileName;
	Size: typeof FileSize;
	Download: typeof FileDownload;
};

File.displayName = "File";
File.Root = FileRoot;
File.Icon = FileIconDisplay;
File.Name = FileName;
File.Size = FileSize;
File.Download = FileDownload;

export {
	File,
	FileDownload,
	FileIconDisplay,
	FileName,
	FileRoot,
	FileSize,
	fileVariants,
	formatFileSize,
	getBase64Size,
	getMimeTypeIcon,
};
