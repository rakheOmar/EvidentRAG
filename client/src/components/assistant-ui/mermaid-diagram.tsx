"use client";

import { useAui, useAuiState } from "@assistant-ui/react";
import type { SyntaxHighlighterProps } from "@assistant-ui/react-markdown";
import { renderMermaidSVG } from "beautiful-mermaid";
import { Maximize2, Minus, Plus, RotateCcw, X } from "lucide-react";
import {
	type FC,
	memo,
	type ReactNode,
	useCallback,
	useEffect,
	useMemo,
	useRef,
	useState,
} from "react";
import { createPortal } from "react-dom";
import { sanitizeSvg } from "@/lib/sanitize-svg";
import { cn } from "@/lib/utils";

export type MermaidDiagramProps = SyntaxHighlighterProps & {
	className?: string;
};

const MIN_SCALE = 0.5;
const MAX_SCALE = 4;

type MermaidZoomProps = {
	svg: string;
	children: ReactNode;
};

function MermaidZoom({ svg, children }: MermaidZoomProps) {
	const [isMounted, setIsMounted] = useState(false);
	const [isOpen, setIsOpen] = useState(false);
	const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 });
	const triggerRef = useRef<HTMLButtonElement>(null);
	const closeRef = useRef<HTMLButtonElement>(null);
	const overlayRef = useRef<HTMLDivElement>(null);
	const viewportRef = useRef<HTMLDivElement>(null);
	const drag = useRef<{
		startX: number;
		startY: number;
		originX: number;
		originY: number;
	} | null>(null);
	const transformRef = useRef(transform);
	transformRef.current = transform;

	const zoomSvg = useMemo(
		() =>
			svg
				.replace(/id="([^"]+)"/g, 'id="$1-zoom"')
				.replace(/url\(#([^)]+)\)/g, "url(#$1-zoom)")
				.replace(/(href|xlink:href)="#([^"]+)"/g, '$1="#$2-zoom"'),
		[svg],
	);

	useEffect(() => {
		setIsMounted(true);
	}, []);

	const handleClose = useCallback(() => {
		setIsOpen(false);
		setTransform({ x: 0, y: 0, scale: 1 });
		triggerRef.current?.focus();
	}, []);

	useEffect(() => {
		if (!isOpen) {
			return;
		}
		const handleKeyDown = (e: KeyboardEvent) => {
			if (e.key === "Escape") {
				handleClose();
				return;
			}
			if (e.key !== "Tab") {
				return;
			}
			const focusables = overlayRef.current?.querySelectorAll<HTMLElement>(
				'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
			);
			if (!focusables?.length) {
				return;
			}
			const first = focusables[0];
			const last = focusables[focusables.length - 1];
			if (e.shiftKey && document.activeElement === first) {
				e.preventDefault();
				last.focus();
			} else if (!e.shiftKey && document.activeElement === last) {
				e.preventDefault();
				first.focus();
			}
		};
		document.addEventListener("keydown", handleKeyDown);
		return () => document.removeEventListener("keydown", handleKeyDown);
	}, [isOpen, handleClose]);

	useEffect(() => {
		if (!isOpen) {
			return;
		}
		const originalOverflow = document.body.style.overflow;
		document.body.style.overflow = "hidden";
		return () => {
			document.body.style.overflow = originalOverflow;
		};
	}, [isOpen]);

	useEffect(() => {
		if (isOpen) {
			closeRef.current?.focus();
		}
	}, [isOpen]);

	const zoomBy = useCallback((factor: number, cx?: number, cy?: number) => {
		setTransform((t) => {
			const scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, t.scale * factor));
			const ratio = scale / t.scale;
			if (cx === undefined || cy === undefined) {
				const viewport = viewportRef.current;
				cx = (viewport?.clientWidth ?? 0) / 2;
				cy = (viewport?.clientHeight ?? 0) / 2;
			}
			return {
				scale,
				x: cx - (cx - t.x) * ratio,
				y: cy - (cy - t.y) * ratio,
			};
		});
	}, []);

	const onWheel = useCallback(
		(e: React.WheelEvent) => {
			const viewport = viewportRef.current;
			if (!viewport) {
				return;
			}
			const rect = viewport.getBoundingClientRect();
			zoomBy(
				Math.exp(-e.deltaY * 0.0015),
				e.clientX - rect.left,
				e.clientY - rect.top,
			);
		},
		[zoomBy],
	);

	const onPointerDown = useCallback((e: React.PointerEvent) => {
		e.currentTarget.setPointerCapture(e.pointerId);
		const t = transformRef.current;
		drag.current = {
			startX: e.clientX,
			startY: e.clientY,
			originX: t.x,
			originY: t.y,
		};
	}, []);

	const onPointerMove = useCallback((e: React.PointerEvent) => {
		const d = drag.current;
		if (!d) {
			return;
		}
		setTransform((t) => ({
			...t,
			x: d.originX + e.clientX - d.startX,
			y: d.originY + e.clientY - d.startY,
		}));
	}, []);

	const onPointerUp = useCallback(() => {
		drag.current = null;
	}, []);

	return (
		<div
			className="aui-mermaid-zoom-wrap group/mermaid relative"
			data-slot="mermaid-zoom-wrap"
		>
			{children}
			<button
				aria-label="Expand diagram"
				className="aui-mermaid-zoom-trigger absolute top-2 right-2 cursor-pointer rounded-md border border-border bg-background p-1.5 text-muted-foreground opacity-0 transition hover:border-muted-foreground/70 hover:text-foreground focus-visible:opacity-100 group-hover/mermaid:opacity-100"
				data-slot="mermaid-zoom-trigger"
				onClick={() => setIsOpen(true)}
				ref={triggerRef}
				type="button"
			>
				<Maximize2 className="size-3.5" />
			</button>
			{isMounted &&
				isOpen &&
				createPortal(
					<div
						aria-label="Diagram"
						aria-modal="true"
						className="aui-mermaid-zoom-overlay fade-in fixed inset-0 z-50 animate-in bg-background duration-200"
						data-slot="mermaid-zoom-overlay"
						ref={overlayRef}
						role="dialog"
					>
						<div
							className="aui-mermaid-zoom-viewport h-full w-full cursor-grab touch-none overflow-hidden active:cursor-grabbing"
							onPointerCancel={onPointerUp}
							onPointerDown={onPointerDown}
							onPointerMove={onPointerMove}
							onPointerUp={onPointerUp}
							onWheel={onWheel}
							ref={viewportRef}
						>
							<div
								className="aui-mermaid-zoom-content flex h-full w-full items-center justify-center [&_svg]:max-h-[80vh] [&_svg]:max-w-[90vw]"
								dangerouslySetInnerHTML={{ __html: sanitizeSvg(zoomSvg) }}
								data-slot="mermaid-zoom-content"
								style={{
									transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.scale})`,
									transformOrigin: "0 0",
								}}
							/>
						</div>
						<div
							className="aui-mermaid-zoom-toolbar absolute top-4 right-4 flex items-center gap-1 rounded-lg border border-border bg-background p-1 shadow-sm"
							data-slot="mermaid-zoom-toolbar"
						>
							<button
								aria-label="Zoom in"
								className="cursor-pointer rounded-sm p-1.5 text-muted-foreground hover:text-foreground"
								onClick={() => zoomBy(1.25)}
								type="button"
							>
								<Plus className="size-4" />
							</button>
							<button
								aria-label="Zoom out"
								className="cursor-pointer rounded-sm p-1.5 text-muted-foreground hover:text-foreground"
								onClick={() => zoomBy(0.8)}
								type="button"
							>
								<Minus className="size-4" />
							</button>
							<button
								aria-label="Reset zoom"
								className="cursor-pointer rounded-sm p-1.5 text-muted-foreground hover:text-foreground"
								onClick={() => setTransform({ x: 0, y: 0, scale: 1 })}
								type="button"
							>
								<RotateCcw className="size-4" />
							</button>
							<button
								aria-label="Close"
								className="cursor-pointer rounded-sm p-1.5 text-muted-foreground hover:text-foreground"
								onClick={handleClose}
								ref={closeRef}
								type="button"
							>
								<X className="size-4" />
							</button>
						</div>
					</div>,
					document.body,
				)}
		</div>
	);
}

/**
 * Use it by passing to `componentsByLanguage` for mermaid in `markdown-text.tsx`.
 *
 * @example
 * const MarkdownTextImpl = () => {
 *   return (
 *     <MarkdownTextPrimitive
 *       remarkPlugins={[remarkGfm]}
 *       className="aui-md"
 *       components={defaultComponents}
 *       componentsByLanguage={{
 *         mermaid: {
 *           SyntaxHighlighter: MermaidDiagram
 *         },
 *       }}
 *     />
 *   );
 * };
 */
const MermaidDiagramImpl: FC<MermaidDiagramProps> = ({
	code,
	className,
	node: _node,
	components: _components,
	language: _language,
}) => {
	const aui = useAui();
	const hasPart = aui.part.source !== null;
	const isComplete = useAuiState(
		(s) => !hasPart || s.part.status.type !== "running",
	);

	const result = useMemo(() => {
		if (!isComplete) {
			return null;
		}
		try {
			return {
				svg: renderMermaidSVG(code, {
					bg: "var(--background)",
					fg: "var(--foreground)",
					muted: "var(--muted-foreground)",
					border: "var(--border)",
					accent: "var(--foreground)",
					transparent: true,
				}),
				error: null,
			};
		} catch (err) {
			return {
				svg: null,
				error: err instanceof Error ? err : new Error(String(err)),
			};
		}
	}, [isComplete, code]);

	if (!result) {
		return (
			<div
				aria-label="Rendering diagram"
				className={cn(
					"aui-mermaid-skeleton flex h-32 animate-pulse items-center justify-center gap-3 rounded-b-lg bg-muted p-4",
					className,
				)}
				data-slot="mermaid-skeleton"
			>
				<div className="h-8 w-20 rounded-md bg-muted-foreground/20" />
				<div className="h-px w-10 bg-muted-foreground/20" />
				<div className="h-8 w-20 rounded-md bg-muted-foreground/20" />
				<div className="h-px w-10 bg-muted-foreground/20" />
				<div className="h-8 w-20 rounded-md bg-muted-foreground/20" />
			</div>
		);
	}

	if (result.error) {
		return (
			<div
				className={cn(
					"aui-mermaid-fallback rounded-b-lg bg-muted/75",
					className,
				)}
				data-slot="mermaid-fallback"
			>
				<pre className="overflow-x-auto p-4 text-sm">{code.trim()}</pre>
				<p className="border-border border-t px-4 py-1.5 text-muted-foreground text-xs">
					diagram could not be rendered
				</p>
			</div>
		);
	}

	return (
		<MermaidZoom svg={result.svg}>
			<div
				className={cn(
					"aui-mermaid-diagram rounded-b-lg bg-muted p-2 [&_svg]:mx-auto",
					className,
				)}
				dangerouslySetInnerHTML={{ __html: sanitizeSvg(result.svg) }}
				data-slot="mermaid-diagram"
			/>
		</MermaidZoom>
	);
};

const MermaidDiagram = memo(
	MermaidDiagramImpl,
) as unknown as FC<MermaidDiagramProps> & {
	Zoom: typeof MermaidZoom;
};

MermaidDiagram.displayName = "MermaidDiagram";
MermaidDiagram.Zoom = MermaidZoom;

export { MermaidDiagram, MermaidZoom };
