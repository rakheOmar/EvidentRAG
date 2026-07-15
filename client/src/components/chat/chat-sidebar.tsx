"use client";

import { ThreadListPrimitive } from "@assistant-ui/react";
import {
	ChevronDownIcon,
	FileTextIcon,
	ListIcon,
	MenuIcon,
	PlusIcon,
} from "lucide-react";
import {
	createContext,
	type Dispatch,
	type FC,
	type ReactNode,
	type SetStateAction,
	useCallback,
	useContext,
	useEffect,
	useState,
} from "react";
import { Link, useLocation } from "react-router";
import {
	ThreadList,
	ThreadListItems,
	ThreadListNew,
	ThreadListRoot,
} from "@/components/assistant-ui/thread-list";
import { Button, buttonVariants } from "@/components/ui/button";
import {
	Collapsible,
	CollapsibleContent,
	CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuRadioGroup,
	DropdownMenuRadioItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import {
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

type SortOrder = "recent" | "oldest";
const SIDEBAR_STORAGE_KEY = "evidentrag:sidebar-collapsed";

interface SidebarState {
	collapsed: boolean;
	setCollapsed: Dispatch<SetStateAction<boolean>>;
}

const SidebarStateContext = createContext<SidebarState | null>(null);

function getInitialSidebarState(): boolean {
	if (typeof window === "undefined") {
		return false;
	}
	return window.localStorage.getItem(SIDEBAR_STORAGE_KEY) === "true";
}

const SidebarStateProvider: FC<{ children: ReactNode }> = ({ children }) => {
	const [collapsed, setCollapsed] = useState(getInitialSidebarState);

	useEffect(() => {
		window.localStorage.setItem(SIDEBAR_STORAGE_KEY, String(collapsed));
	}, [collapsed]);

	return (
		<SidebarStateContext.Provider value={{ collapsed, setCollapsed }}>
			{children}
		</SidebarStateContext.Provider>
	);
};

const useSidebarState = () => {
	const context = useContext(SidebarStateContext);
	if (!context) {
		throw new Error("useSidebarState must be used within SidebarStateProvider");
	}
	return context;
};

const ChatHistorySection: FC = () => {
	const [open, setOpen] = useState(true);
	const [sortOrder, setSortOrder] = useState<SortOrder>("recent");
	const handleSortOrderChange = useCallback((value: string) => {
		setSortOrder(value as SortOrder);
	}, []);

	return (
		<Collapsible
			data-slot="chat-history-section"
			onOpenChange={setOpen}
			open={open}
		>
			<div className="group/section-header flex min-h-8 items-center gap-1 px-2.5">
				<CollapsibleTrigger
					render={
						<button
							className="flex h-8 min-w-0 flex-1 items-center justify-start gap-0.5 text-muted-foreground"
							type="button"
						>
							<h2
								className="font-semibold text-foreground text-xs"
								data-no-spacing="true"
							>
								Chats
							</h2>
							<ChevronDownIcon
								className={cn(
									"h-3 w-3 shrink-0 opacity-0 transition-transform group-hover/section-header:opacity-100",
									open ? "rotate-0" : "-rotate-90",
								)}
							/>
						</button>
					}
				/>
				<div className="flex shrink-0 items-center gap-1">
					<ThreadListPrimitive.New asChild>
						<Button
							aria-label="New chat"
							className="size-7 opacity-0 transition-opacity focus-visible:opacity-100 group-hover/section-header:opacity-100 data-[state=open]:opacity-100"
							size="icon"
							variant="ghost"
						>
							<PlusIcon className="size-4" />
						</Button>
					</ThreadListPrimitive.New>
					<DropdownMenu>
						<DropdownMenuTrigger
							render={
								<Button
									aria-label="Organize chats"
									className="size-7 opacity-0 transition-opacity focus-visible:opacity-100 group-hover/section-header:opacity-100 data-[state=open]:opacity-100"
									size="icon"
									variant="ghost"
								>
									<ListIcon className="size-4" />
								</Button>
							}
						/>
						<DropdownMenuContent
							align="start"
							className="min-w-40"
							side="right"
							sideOffset={6}
						>
							<DropdownMenuRadioGroup
								onValueChange={handleSortOrderChange}
								value={sortOrder}
							>
								<DropdownMenuRadioItem value="recent">
									Recently updated
								</DropdownMenuRadioItem>
								<DropdownMenuRadioItem value="oldest">
									Oldest
								</DropdownMenuRadioItem>
							</DropdownMenuRadioGroup>
						</DropdownMenuContent>
					</DropdownMenu>
				</div>
			</div>
			<CollapsibleContent className="flex flex-col gap-0.5">
				<ThreadListItems sortOrder={sortOrder} />
			</CollapsibleContent>
		</Collapsible>
	);
};

const BrandLogo: FC = () => (
	<>
		<img
			alt="EvidentRAG"
			className="h-7 w-auto dark:hidden"
			height={586}
			src="/brand/logo_light.png"
			width={2717}
		/>
		<img
			alt="EvidentRAG"
			className="hidden h-7 w-auto dark:block"
			height={586}
			src="/brand/logo_dark.png"
			width={2717}
		/>
	</>
);

const BrandIcon: FC = () => (
	<>
		<img
			alt="EvidentRAG"
			className="h-6 w-auto object-contain dark:hidden"
			height={639}
			src="/brand/icon_light.png"
			width={500}
		/>
		<img
			alt="EvidentRAG"
			className="hidden h-6 w-auto object-contain dark:block"
			height={639}
			src="/brand/icon_dark.png"
			width={500}
		/>
	</>
);

const Logo: FC = () => (
	<div className="flex items-center justify-center font-medium text-sm">
		<BrandLogo />
	</div>
);

const DocumentsNavigation: FC<{ collapsed?: boolean }> = ({ collapsed }) => {
	const { pathname } = useLocation();

	const isActive = pathname === "/documents";

	const link = (
		<Link
			aria-current={isActive ? "page" : undefined}
			aria-label="Documents"
			className={cn(
				buttonVariants({ variant: "ghost" }),
				"h-8 justify-start gap-2 overflow-hidden rounded-md px-2.5 font-normal text-sm hover:bg-muted data-active:bg-muted",
				collapsed ? "w-8 px-2.5" : "w-full",
				isActive && "data-active",
			)}
			data-active={isActive}
			to="/documents"
		>
			<FileTextIcon className="size-4 shrink-0" />
			<span
				className={cn(
					"whitespace-nowrap transition-[max-width,opacity] duration-200",
					collapsed
						? "max-w-0 overflow-hidden opacity-0"
						: "max-w-24 opacity-100",
				)}
			>
				Documents
			</span>
		</Link>
	);

	if (!collapsed) {
		return link;
	}

	return (
		<Tooltip>
			<TooltipTrigger render={link} />
			<TooltipContent side="right">Documents</TooltipContent>
		</Tooltip>
	);
};

const Sidebar: FC<{ collapsed?: boolean }> = ({ collapsed }) => (
	<aside
		className={cn(
			"flex h-full flex-col overflow-hidden rounded-lg bg-muted/30 transition-[width] duration-200",
			collapsed ? "w-12" : "w-65",
		)}
	>
		<div
			className={cn(
				"mt-2 flex h-12 shrink-0 items-center justify-center transition-[padding] duration-200",
				collapsed ? "px-0" : "px-6",
			)}
		>
			{collapsed ? <BrandIcon /> : <BrandLogo />}
		</div>
		<ThreadListRoot
			className={cn(
				"relative flex-1 overflow-y-auto transition-[padding,width] duration-200",
				collapsed ? "w-12 px-2 py-2" : "w-65 p-3",
			)}
		>
			{collapsed ? (
				<Tooltip>
					<TooltipTrigger
						render={
							<ThreadListNew
								className="w-8 gap-0 overflow-hidden px-2 transition-[width,padding,gap] duration-200 has-[>svg]:px-2"
								labelClassName="max-w-0 overflow-hidden opacity-0 transition-[max-width,opacity] duration-200"
								title="New Query"
							/>
						}
					/>
					<TooltipContent side="right">New Query</TooltipContent>
				</Tooltip>
			) : (
				<ThreadListNew
					className="w-full gap-2 overflow-hidden px-2.5 transition-[width,padding,gap] duration-200 has-[>svg]:px-2.5"
					labelClassName="max-w-24 overflow-hidden opacity-100 transition-[max-width,opacity] duration-200"
					title="New Query"
				/>
			)}
			<DocumentsNavigation collapsed={collapsed} />
			{collapsed ? (
				<ThreadListItems
					aria-hidden
					className="pointer-events-none opacity-0 delay-50"
					inert
				/>
			) : (
				<ChatHistorySection />
			)}
		</ThreadListRoot>
	</aside>
);

const MobileSidebar: FC = () => (
	<Sheet>
		<SheetTrigger
			render={
				<Button
					className="size-8 shrink-0 md:hidden"
					size="icon"
					variant="ghost"
				>
					<MenuIcon className="size-4" />
					<span className="sr-only">Toggle menu</span>
				</Button>
			}
		/>
		<SheetContent className="flex w-70 flex-col p-0" side="left">
			<div className="flex h-12 shrink-0 items-center justify-center px-4">
				<Logo />
			</div>
			<div className="relative flex-1 overflow-y-auto p-3">
				<DocumentsNavigation />
				<ThreadList />
			</div>
		</SheetContent>
	</Sheet>
);

const AppShell: FC<{ collapsed?: boolean; children: ReactNode }> = ({
	children,
	collapsed,
}) => {
	const sidebarState = useSidebarState();

	return (
		<div className="flex h-full w-full bg-muted/30">
			<div className="hidden md:block">
				<Sidebar collapsed={collapsed ?? sidebarState.collapsed} />
			</div>
			<div className="flex flex-1 flex-col overflow-hidden p-2 md:pl-0">
				{children}
			</div>
		</div>
	);
};

export {
	AppShell,
	Logo,
	MobileSidebar,
	Sidebar,
	SidebarStateProvider,
	useSidebarState,
};
