"use client";

import {
	AuiIf,
	ThreadListItemPrimitive,
	ThreadListPrimitive,
	useAuiState,
} from "@assistant-ui/react";
import {
	ArchiveIcon,
	MoreHorizontalIcon,
	PlusIcon,
	TrashIcon,
} from "lucide-react";
import {
	type ComponentPropsWithoutRef,
	type FC,
	Fragment,
	forwardRef,
	useMemo,
} from "react";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export const ThreadList: FC = () => (
	<ThreadListRoot>
		<ThreadListNew />
		<ThreadListItems />
	</ThreadListRoot>
);

export const ThreadListRoot: FC<
	ComponentPropsWithoutRef<typeof ThreadListPrimitive.Root>
> = ({ className, ...props }) => (
	<ThreadListPrimitive.Root
		className={cn("flex flex-col gap-0.5", className)}
		data-slot="aui_thread-list-root"
		{...props}
	/>
);

export const ThreadListItems: FC<
	ComponentPropsWithoutRef<"div"> & { sortOrder?: "recent" | "oldest" }
> = ({ className, sortOrder = "recent", ...props }) => (
	<div
		className={cn("flex flex-col gap-0.5", className)}
		data-slot="aui_thread-list-items"
		{...props}
	>
		<AuiIf condition={(s) => s.threads.isLoading}>
			<ThreadListSkeleton />
		</AuiIf>
		<AuiIf condition={(s) => !s.threads.isLoading}>
			<ThreadListItemGroups sortOrder={sortOrder} />
		</AuiIf>
	</div>
);

const DAY_IN_MS = 86_400_000;

const dateGroupLabel = (
	date: Date | undefined,
	startOfToday: number,
): string => {
	if (!date || date.getTime() >= startOfToday) {
		return "Today";
	}
	if (date.getTime() >= startOfToday - DAY_IN_MS) {
		return "Yesterday";
	}
	return "Earlier";
};

type ThreadListGroup = { label: string; indices: number[] };

const ThreadListItemGroups: FC<{ sortOrder: "recent" | "oldest" }> = ({
	sortOrder,
}) => {
	const threadIds = useAuiState((s) => s.threads.threadIds);
	const threadItems = useAuiState((s) => s.threads.threadItems);

	const groups = useMemo<ThreadListGroup[] | null>(() => {
		const itemsById = new Map(threadItems.map((item) => [item.id, item]));
		const dates = threadIds.map((id) => itemsById.get(id)?.lastMessageAt);
		if (!dates.some(Boolean)) {
			return null;
		}

		const now = new Date();
		const startOfToday = new Date(
			now.getFullYear(),
			now.getMonth(),
			now.getDate(),
		).getTime();
		const time = (index: number) =>
			dates[index]?.getTime() ?? Number.MAX_SAFE_INTEGER;
		const indices = threadIds
			.map((_, index) => index)
			.sort((a, b) =>
				sortOrder === "oldest" ? time(a) - time(b) : time(b) - time(a),
			);

		const result: ThreadListGroup[] = [];
		for (const index of indices) {
			const label = dateGroupLabel(dates[index], startOfToday);
			const lastGroup = result[result.length - 1];
			if (lastGroup?.label === label) {
				lastGroup.indices.push(index);
			} else {
				result.push({ label, indices: [index] });
			}
		}
		return result;
	}, [sortOrder, threadIds, threadItems]);

	if (!groups) {
		return (
			<ThreadListPrimitive.Items>
				{() => <ThreadListItem />}
			</ThreadListPrimitive.Items>
		);
	}

	return groups.map((group) => (
		<Fragment key={group.label}>
			<div
				className="px-2.5 pt-3 pb-1 font-medium text-muted-foreground text-xs"
				data-slot="aui_thread-list-group-label"
			>
				{group.label}
			</div>
			{group.indices.map((index) => (
				<ThreadListPrimitive.ItemByIndex
					components={{ ThreadListItem }}
					index={index}
					key={threadIds[index]}
				/>
			))}
		</Fragment>
	));
};

export const ThreadListNew = forwardRef<
	HTMLButtonElement,
	ComponentPropsWithoutRef<typeof Button> & { labelClassName?: string }
>(({ className, labelClassName, children, ...props }, ref) => (
	<ThreadListPrimitive.New asChild>
		<Button
			className={cn(
				"h-8 justify-start gap-2 rounded-md px-2.5 font-normal text-sm hover:bg-muted data-active:bg-muted",
				className,
			)}
			data-slot="aui_thread-list-new"
			ref={ref}
			variant="ghost"
			{...props}
		>
			{children ?? (
				<>
					<PlusIcon
						className="size-4 shrink-0"
						data-slot="aui_thread-list-new-icon"
					/>
					<span
						className={cn("whitespace-nowrap", labelClassName)}
						data-slot="aui_thread-list-new-label"
					>
						New Thread
					</span>
				</>
			)}
		</Button>
	</ThreadListPrimitive.New>
));

ThreadListNew.displayName = "ThreadListNew";

const ThreadListSkeleton: FC = () => (
	<div className="flex flex-col gap-0.5">
		{Array.from({ length: 5 }, (_, i) => (
			<div
				aria-label="Loading threads"
				className="flex h-8 items-center px-2.5"
				data-slot="aui_thread-list-skeleton-wrapper"
				key={`skeleton-${i}`}
				role="status"
			>
				<Skeleton
					className="h-3.5 w-full"
					data-slot="aui_thread-list-skeleton"
				/>
			</div>
		))}
	</div>
);

export const ThreadListItem: FC = () => (
	<ThreadListItemPrimitive.Root
		className="group relative flex h-8 items-center rounded-md transition-colors hover:bg-muted focus-visible:bg-muted focus-visible:outline-none has-data-[state=open]:bg-muted has-focus-visible:bg-muted data-active:bg-muted"
		data-slot="aui_thread-list-item"
	>
		<ThreadListItemPrimitive.Trigger
			className="flex h-full min-w-0 flex-1 items-center rounded-md px-2.5 text-start text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 group-hover:pe-9 group-has-data-[state=open]:pe-9 group-has-focus-visible:pe-9 group-data-active:pe-9"
			data-slot="aui_thread-list-item-trigger"
		>
			<span
				className="min-w-0 flex-1 truncate"
				data-slot="aui_thread-list-item-title"
			>
				<ThreadListItemPrimitive.Title fallback="New Chat" />
			</span>
		</ThreadListItemPrimitive.Trigger>
		<ThreadListItemMore />
	</ThreadListItemPrimitive.Root>
);

const ThreadListItemMore: FC = () => (
	<DropdownMenu>
		<DropdownMenuTrigger
			render={
				<Button
					className="absolute end-1.5 top-1/2 size-6 -translate-y-1/2 p-0 opacity-0 group-hover:opacity-100 group-has-focus-visible:opacity-100 data-[state=open]:bg-accent data-[state=open]:opacity-100 group-data-active:opacity-100"
					data-slot="aui_thread-list-item-more"
					size="icon"
					variant="ghost"
				>
					<MoreHorizontalIcon className="size-3.5" />
					<span className="sr-only">More options</span>
				</Button>
			}
		/>
		<DropdownMenuContent
			align="start"
			className="min-w-40"
			side="right"
			sideOffset={6}
		>
			<ThreadListItemPrimitive.Archive asChild>
				<DropdownMenuItem>
					<ArchiveIcon className="size-4" />
					Archive
				</DropdownMenuItem>
			</ThreadListItemPrimitive.Archive>
			<ThreadListItemPrimitive.Delete asChild>
				<DropdownMenuItem className="text-destructive data-[highlighted]:bg-destructive/10 data-[highlighted]:text-destructive">
					<TrashIcon className="size-4" />
					Delete
				</DropdownMenuItem>
			</ThreadListItemPrimitive.Delete>
		</DropdownMenuContent>
	</DropdownMenu>
);
