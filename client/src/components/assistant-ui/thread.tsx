"use client";

import {
  ActionBarMorePrimitive,
  ActionBarPrimitive,
  type AssistantState,
  AuiIf,
  ComposerPrimitive,
  ErrorPrimitive,
  groupPartByType,
  MessagePrimitive,
  SuggestionPrimitive,
  ThreadPrimitive,
  type ToolCallMessagePartComponent,
  useAuiState,
} from "@assistant-ui/react";
import {
  Copy01Icon,
  CopyCheckIcon,
  Download01Icon,
  Flowchart02Icon,
  GitCompareIcon,
  GitBranchIcon as HugeGitBranchIcon,
  MoreHorizontalIcon as HugeMoreHorizontalIcon,
  SparklesIcon as HugeSparklesIcon,
  ThumbsDownIcon as HugeThumbsDownIcon,
  ThumbsUpIcon as HugeThumbsUpIcon,
  Layers01Icon,
  Message02Icon,
  Refresh01Icon,
  Route01Icon,
  Search01Icon,
  Sorting01Icon,
} from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import {
  ArrowDownIcon,
  ArrowUpIcon,
  MicIcon,
  PencilIcon,
  SquareIcon,
} from "lucide-react";
import {
  type ComponentType,
  createContext,
  type FC,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  ComposerAddAttachment,
  ComposerAttachments,
  UserMessageAttachments,
} from "@/components/assistant-ui/attachment";
import {
  ChainOfThought,
  ChainOfThoughtContent,
  ChainOfThoughtHeader,
  ChainOfThoughtSearchResults,
  ChainOfThoughtStep,
} from "@/components/assistant-ui/chain-of-thought";
import { InlineCitationText } from "@/components/assistant-ui/inline-citations";
import { MarkdownText } from "@/components/assistant-ui/markdown-text";
import { Sources } from "@/components/assistant-ui/sources";
import { ToolFallback } from "@/components/assistant-ui/tool-fallback";
import {
  ToolGroupContent,
  ToolGroupRoot,
  ToolGroupTrigger,
} from "@/components/assistant-ui/tool-group";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
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
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from "@/components/ui/popover";
import { putSentenceTraceFeedback } from "@/lib/api";
import { getMessageSegments, updateSegmentRating } from "@/lib/segments-store";
import {
  hasRichMarkdown,
  isSegmentHighlighted,
  requiresFullWidthHighlight,
} from "@/lib/markdown";
import type { QueryRoute } from "@/lib/types";
import { cn } from "@/lib/utils";

type MessageMetadataCustom = {
  hopProgress?: {
    hop: number;
    intermediate_answer: string;
    sub_query: string;
  }[];
  reasoningTrace?: {
    type: "step" | "hop" | "retrieval";
    text?: string;
    hop?: number;
    sub_query?: string;
    intermediate_answer?: string;
    label?: string;
    candidates?: {
      document_title: string;
      evidence_id: string;
      page: number;
      snippet: string;
    }[];
  }[];
  route?: QueryRoute;
  subQueries?: string[];
  generating?: boolean;
};

type ReasoningTraceEntry = NonNullable<
  MessageMetadataCustom["reasoningTrace"]
>[number];

type RetrievalCandidateEntry = NonNullable<
  ReasoningTraceEntry["candidates"]
>[number];

function formatRouteLabel(route: QueryRoute): string {
  switch (route) {
    case "multi_hop":
      return "Multi-step";
    case "comparison":
      return "Compare";
    case "aggregation":
      return "Synthesis";
    case "conversation":
      return "From chat";
    default:
      return "Direct";
  }
}

function formatTraceLabel(text: string): string {
  const normalized = text.toLowerCase();
  if (normalized.includes("routing")) return "Choosing the best route";
  if (normalized.includes("retrieving evidence"))
    return "Searching your evidence";
  if (normalized.includes("fusing")) return "Blending search results";
  if (normalized.includes("reranking")) return "Ranking the strongest passages";
  if (normalized.includes("generating answer from thread memory")) {
    return "Writing from thread memory";
  }
  if (normalized.includes("reading prior turns"))
    return "Reading thread memory";
  if (normalized.includes("generating answer")) return "Writing the answer";
  if (normalized.includes("comparison:"))
    return "Comparing the relevant evidence";
  if (normalized.includes("aggregation:"))
    return "Synthesizing across the evidence";
  return text.replace(/\.\.\.$/, "");
}

function routeBadgeClassName(route: QueryRoute): string {
  switch (route) {
    case "multi_hop":
      return "bg-blue-500/12 text-blue-700 dark:text-blue-300";
    case "comparison":
      return "bg-violet-500/12 text-violet-700 dark:text-violet-300";
    case "aggregation":
      return "bg-emerald-500/12 text-emerald-700 dark:text-emerald-300";
    case "conversation":
      return "bg-amber-500/12 text-amber-700 dark:text-amber-300";
    default:
      return "bg-primary/10 text-primary";
  }
}

function routeIcon(route: QueryRoute) {
  switch (route) {
    case "multi_hop":
      return GitCompareIcon;
    case "comparison":
      return GitCompareIcon;
    case "aggregation":
      return Layers01Icon;
    case "conversation":
      return Message02Icon;
    default:
      return Route01Icon;
  }
}

export type ThreadGroupPart = MessagePrimitive.GroupedParts.GroupPart;

/**
 * Optional component overrides for the thread. `AssistantMessage` and
 * `Welcome` replace whole sections; the remaining slots override how the
 * assistant message renders tool calls and part groups. Tool UIs registered
 * by name (toolkit `render`, `useAssistantDataUI`) take precedence over
 * `ToolFallback`.
 */
export type ThreadComponents = {
  AssistantMessage?: ComponentType | undefined;
  Welcome?: ComponentType | undefined;
  ToolFallback?: ToolCallMessagePartComponent | undefined;
  ToolGroup?:
    ComponentType<PropsWithChildren<{ group: ThreadGroupPart }>> | undefined;
  ReasoningGroup?:
    ComponentType<PropsWithChildren<{ group: ThreadGroupPart }>> | undefined;
};

export type ThreadProps = {
  components?: ThreadComponents | undefined;
};

const EMPTY_COMPONENTS: ThreadComponents = {};

const ThreadComponentsContext =
  createContext<ThreadComponents>(EMPTY_COMPONENTS);

// Startup exposes a loading placeholder thread; treat it as a new chat so
// the composer mounts centered. Loads after startup keep the docked layout.
const isNewChatView = (s: AssistantState) =>
  s.thread.messages.length === 0 &&
  (!s.thread.isLoading || s.threads.isLoading);

export const Thread: FC<ThreadProps> = ({ components = EMPTY_COMPONENTS }) => {
  const isEmpty = useAuiState(isNewChatView);

  return (
    <ThreadComponentsContext.Provider value={components}>
      <ThreadRoot isEmpty={isEmpty} />
    </ThreadComponentsContext.Provider>
  );
};

const ThreadRoot: FC<{ isEmpty: boolean }> = ({ isEmpty }) => {
  const { Welcome = ThreadWelcome } = useContext(ThreadComponentsContext);

  return (
    <ThreadPrimitive.Root
      className="aui-root aui-thread-root @container flex h-full flex-col bg-background"
      style={{
        ["--thread-max-width" as string]: "44rem",
        ["--composer-bg" as string]:
          "color-mix(in oklab, var(--color-muted) 30%, var(--color-background))",
        ["--composer-radius" as string]: "1.5rem",
        ["--composer-padding" as string]: "8px",
      }}
    >
      <ThreadPrimitive.Viewport
        className="relative flex flex-1 flex-col overflow-x-auto overflow-y-scroll scroll-smooth md:scrollbar-none md:[&::-webkit-scrollbar]:hidden"
        data-slot="aui_thread-viewport"
        turnAnchor="top"
      >
        <div
          className={cn(
            "mx-auto flex w-full max-w-(--thread-max-width) flex-1 flex-col px-4 pt-4",
            isEmpty && "justify-center",
          )}
        >
          <AuiIf condition={isNewChatView}>
            <Welcome />
          </AuiIf>

          <div
            className="mb-14 flex flex-col gap-y-6 empty:hidden"
            data-slot="aui_message-group"
          >
            <ThreadPrimitive.Messages>
              {() => <ThreadMessage />}
            </ThreadPrimitive.Messages>
          </div>

          <ThreadPrimitive.ViewportFooter
            className={cn(
              "aui-thread-viewport-footer flex flex-col gap-4 overflow-visible bg-background pb-4 md:pb-6",
              !isEmpty &&
                "sticky bottom-0 mt-auto rounded-t-(--composer-radius)",
            )}
          >
            <ThreadScrollToBottom />
            <Composer />
            <div className={cn(isEmpty && "min-h-10")}>
              <AuiIf condition={(s) => isNewChatView(s) && s.composer.isEmpty}>
                <ThreadSuggestions />
              </AuiIf>
            </div>
          </ThreadPrimitive.ViewportFooter>
        </div>
      </ThreadPrimitive.Viewport>
    </ThreadPrimitive.Root>
  );
};

const ThreadMessage: FC = () => {
  const { AssistantMessage: AssistantMessageComponent = AssistantMessage } =
    useContext(ThreadComponentsContext);
  const role = useAuiState((s) => s.message.role);
  const isEditing = useAuiState((s) => s.message.composer.isEditing);

  if (isEditing) {
    return <EditComposer />;
  }
  if (role === "user") {
    return <UserMessage />;
  }
  return <AssistantMessageComponent />;
};

const ThreadScrollToBottom: FC = () => (
  <ThreadPrimitive.ScrollToBottom asChild>
    <TooltipIconButton
      className="aui-thread-scroll-to-bottom absolute -top-12 z-10 self-center rounded-full p-4 disabled:invisible dark:border-border dark:bg-background dark:hover:bg-accent"
      tooltip="Scroll to bottom"
      variant="outline"
    >
      <ArrowDownIcon />
    </TooltipIconButton>
  </ThreadPrimitive.ScrollToBottom>
);

const ThreadWelcome: FC = () => (
  <div className="aui-thread-welcome-root mb-6 flex flex-col items-center px-4 text-center">
    <h1 className="aui-thread-welcome-message-inner fade-in slide-in-from-bottom-1 animate-in fill-mode-both font-semibold text-2xl duration-200">
      How can I help you today?
    </h1>
  </div>
);

const ThreadSuggestions: FC = () => (
  <div className="aui-thread-welcome-suggestions flex w-full flex-wrap items-center justify-center gap-2 px-4">
    <ThreadPrimitive.Suggestions>
      {() => <ThreadSuggestionItem />}
    </ThreadPrimitive.Suggestions>
  </div>
);

const ThreadSuggestionItem: FC = () => (
  <div className="aui-thread-welcome-suggestion-display fade-in slide-in-from-bottom-2 animate-in fill-mode-both duration-200">
    <SuggestionPrimitive.Trigger asChild send>
      <Button
        className="aui-thread-welcome-suggestion h-auto gap-1.5 whitespace-nowrap rounded-full border border-border/60 px-3.5 py-1.5 font-normal text-foreground text-sm transition-colors hover:bg-muted"
        variant="ghost"
      >
        <SuggestionPrimitive.Title className="aui-thread-welcome-suggestion-text-1" />
        <SuggestionPrimitive.Description className="aui-thread-welcome-suggestion-text-2 empty:hidden" />
      </Button>
    </SuggestionPrimitive.Trigger>
  </div>
);

const Composer: FC = () => (
  <ComposerPrimitive.Root className="aui-composer-root relative flex w-full flex-col">
    <ComposerPrimitive.AttachmentDropzone asChild>
      <div
        className="flex w-full flex-col gap-2 rounded-(--composer-radius) border border-border/60 bg-(--composer-bg) p-(--composer-padding) shadow-[0_4px_16px_-8px_rgba(0,0,0,0.08),0_1px_2px_rgba(0,0,0,0.04)] transition-[border-color,box-shadow] focus-within:border-border focus-within:shadow-[0_6px_24px_-8px_rgba(0,0,0,0.12),0_1px_2px_rgba(0,0,0,0.05)] data-[dragging=true]:border-ring data-[dragging=true]:border-dashed data-[dragging=true]:bg-[color-mix(in_oklab,var(--color-accent)_50%,var(--color-background))] dark:border-muted-foreground/15 dark:shadow-none dark:focus-within:border-muted-foreground/30"
        data-slot="aui_composer-shell"
      >
        <ComposerAttachments />
        <ComposerPrimitive.Input
          aria-label="Message input"
          autoFocus
          className="aui-composer-input max-h-32 min-h-10 w-full resize-none overflow-y-auto bg-transparent px-2.5 py-1 text-base leading-6 outline-none placeholder:text-muted-foreground/80"
          placeholder="Send a message..."
          rows={1}
        />
        <ComposerAction />
      </div>
    </ComposerPrimitive.AttachmentDropzone>
  </ComposerPrimitive.Root>
);

const ComposerAction: FC = () => (
  <div className="aui-composer-action-wrapper relative flex items-center justify-between">
    <ComposerAddAttachment />
    <div className="flex items-center gap-1.5">
      <AuiIf condition={(s) => s.thread.capabilities.dictation}>
        <AuiIf condition={(s) => s.composer.dictation == null}>
          <ComposerPrimitive.Dictate asChild>
            <TooltipIconButton
              aria-label="Start voice input"
              className="aui-composer-dictate size-7 rounded-full"
              side="bottom"
              size="icon"
              tooltip="Voice input"
              type="button"
              variant="ghost"
            >
              <MicIcon className="aui-composer-dictate-icon size-4" />
            </TooltipIconButton>
          </ComposerPrimitive.Dictate>
        </AuiIf>
        <AuiIf condition={(s) => s.composer.dictation != null}>
          <ComposerPrimitive.StopDictation asChild>
            <TooltipIconButton
              aria-label="Stop voice input"
              className="aui-composer-stop-dictation size-7 rounded-full text-destructive"
              side="bottom"
              size="icon"
              tooltip="Stop dictation"
              type="button"
              variant="ghost"
            >
              <SquareIcon className="aui-composer-stop-dictation-icon size-3.5 animate-pulse fill-current" />
            </TooltipIconButton>
          </ComposerPrimitive.StopDictation>
        </AuiIf>
      </AuiIf>
      <AuiIf condition={(s) => !s.thread.isRunning}>
        <ComposerPrimitive.Send asChild>
          <TooltipIconButton
            aria-label="Send message"
            className="aui-composer-send size-7 rounded-full"
            side="bottom"
            size="icon"
            tooltip="Send message"
            type="button"
            variant="default"
          >
            <ArrowUpIcon className="aui-composer-send-icon size-4.5" />
          </TooltipIconButton>
        </ComposerPrimitive.Send>
      </AuiIf>
      <AuiIf condition={(s) => s.thread.isRunning}>
        <ComposerPrimitive.Cancel asChild>
          <Button
            aria-label="Stop generating"
            className="aui-composer-cancel size-7 rounded-full"
            size="icon"
            type="button"
            variant="default"
          >
            <SquareIcon className="aui-composer-cancel-icon size-3.5 fill-current" />
          </Button>
        </ComposerPrimitive.Cancel>
      </AuiIf>
    </div>
  </div>
);

const MessageError: FC = () => (
  <MessagePrimitive.Error>
    <ErrorPrimitive.Root className="aui-message-error-root mt-2 rounded-md border border-destructive bg-destructive/10 p-3 text-destructive text-sm dark:bg-destructive/5 dark:text-red-200">
      <ErrorPrimitive.Message className="aui-message-error-message line-clamp-2" />
    </ErrorPrimitive.Root>
  </MessagePrimitive.Error>
);

const TextWithCitations: FC = () => {
  const messageId = useAuiState((s) => s.message.id);
  const segments = getMessageSegments(messageId);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const { selectedEvidenceIds, selectEvidence, clearEvidence } =
    useEvidencePanel();

  const selectedEvidenceSet = useMemo(
    () => new Set(selectedEvidenceIds),
    [selectedEvidenceIds],
  );

  const evidenceNumbers = useMemo(() => {
    const order: string[] = [];
    const seen = new Set<string>();
    for (const seg of segments ?? []) {
      for (const id of seg.evidence_ids) {
        if (!seen.has(id)) {
          seen.add(id);
          order.push(id);
        }
      }
    }
    return new Map(order.map((id, i) => [id, i + 1]));
  }, [segments]);

  const renderedSegments = useMemo(() => {
    if (!segments) {
      return [];
    }

    return segments.map((seg, index) => {
      const previousText = index > 0 ? (segments[index - 1]?.text ?? "") : "";
      const needsLeadingSpace =
        index > 0 &&
        previousText.length > 0 &&
        seg.text.length > 0 &&
        !/\s$/.test(previousText) &&
        !/^\s/.test(seg.text) &&
        /[A-Za-z0-9).,!?:;"']$/.test(previousText) &&
        /^[A-Za-z0-9("']/.test(seg.text);

      return {
        ...seg,
        text: needsLeadingSpace ? ` ${seg.text}` : seg.text,
      };
    });
  }, [segments]);

  const renderAsMarkdown = useMemo(
    () => (segments ?? []).some((segment) => hasRichMarkdown(segment.text)),
    [segments],
  );
  const toggleEvidence = useCallback(
    (id: string) => {
      if (
        selectedEvidenceIds.length === 1 &&
        selectedEvidenceIds[0] === id
      ) {
        clearEvidence();
        return;
      }
      selectEvidence(messageId, [id]);
    },
    [clearEvidence, messageId, selectEvidence, selectedEvidenceIds],
  );

  const renderCitationButtons = (evidenceIds: string[]) => {
    const uniqueIds = [...new Set(evidenceIds)];
    if (uniqueIds.length === 0) {
      return null;
    }
    return (
      <span className="inline-flex items-center gap-1 align-middle">
        {uniqueIds.map((id) => {
          const number = evidenceNumbers.get(id);
          const isSelected = selectedEvidenceSet.has(id);
          return (
            <Badge
              aria-label={`View evidence ${number ?? ""}`.trim()}
              aria-pressed={isSelected}
              className="ml-0.5 cursor-pointer rounded-full transition-[background-color,color,transform] duration-150 active:scale-[0.96]"
              data-evidence-id={id}
              key={id}
              onClick={() => toggleEvidence(id)}
              onMouseEnter={() => setHoveredId(id)}
              onMouseLeave={() => setHoveredId(null)}
              render={<button type="button" />}
              variant={isSelected ? "default" : "secondary"}
            >
              {number}
            </Badge>
          );
        })}
      </span>
    );
  };

  if (segments && segments.length > 0) {
    return (
      <>
        {renderAsMarkdown ? (
          <div className="space-y-3">
            {renderedSegments.map((seg) => {
              const isHighlighted = isSegmentHighlighted(
                seg.evidence_ids,
                hoveredId,
                selectedEvidenceIds,
              );
              const usesFullWidthHighlight = requiresFullWidthHighlight(
                seg.text,
              );

              return (
                <div
                  className={cn(
                    "transition-colors duration-150",
                    usesFullWidthHighlight
                      ? "w-full"
                      : "-mx-0.5 w-fit max-w-full rounded-sm px-0.5",
                    isHighlighted && "bg-accent",
                  )}
                  data-segment-index={seg.segment_index}
                  key={seg.segment_index}
                >
                  <MarkdownText content={seg.text} />
                </div>
              );
            })}
          </div>
        ) : (
          renderedSegments.map((seg) => {
            const isHighlighted = isSegmentHighlighted(
              seg.evidence_ids,
              hoveredId,
              selectedEvidenceIds,
            );

            return (
              <span key={seg.segment_index}>
                <InlineCitationText
                  className={cn(
                    "-mx-0.5 box-decoration-clone rounded-sm px-0.5",
                    isHighlighted && "bg-accent",
                  )}
                >
                  {seg.text}
                </InlineCitationText>
              </span>
            );
          })
        )}
        {evidenceNumbers.size > 0 && (
          <span className="ms-1 inline-flex items-center gap-0.5 align-baseline">
            {renderCitationButtons([...evidenceNumbers.keys()])}
          </span>
        )}
      </>
    );
  }

  return <MarkdownText />;
};

const SentenceFeedbackPopover: FC = () => {
  const messageId = useAuiState((s) => s.message.id);
  const segments = getMessageSegments(messageId);
  const [pendingTraceId, setPendingTraceId] = useState<string | null>(null);

  const rateableSegments = useMemo(
    () => (segments ?? []).filter((segment) => segment.evidence_ids.length > 0),
    [segments],
  );

  const handleFeedback = useCallback(
    async (traceId: string, rating: "up" | "down") => {
      setPendingTraceId(traceId);
      try {
        await putSentenceTraceFeedback(traceId, rating);
        updateSegmentRating(messageId, traceId, rating);
      } finally {
        setPendingTraceId(null);
      }
    },
    [messageId],
  );

  if (rateableSegments.length === 0) {
    return null;
  }

  return (
    <Popover>
      <PopoverTrigger
        render={
          <TooltipIconButton
            aria-label="Rate evidence"
            className="data-[state=open]:bg-accent"
            tooltip="Rate evidence"
          >
            <HugeiconsIcon icon={HugeThumbsUpIcon} strokeWidth={1.8} />
          </TooltipIconButton>
        }
      />
      <PopoverContent
        align="start"
        className="w-[min(22rem,calc(100vw-2rem))] gap-3 rounded-2xl p-3 shadow-xl"
        side="top"
        sideOffset={8}
      >
        <PopoverHeader className="px-1">
          <div className="flex items-center justify-between gap-3">
            <PopoverTitle>Rate evidence</PopoverTitle>
            <span className="tabular-nums text-muted-foreground text-xs">
              {rateableSegments.length} cited
            </span>
          </div>
          <PopoverDescription className="text-xs">
            Which parts helped answer your question?
          </PopoverDescription>
        </PopoverHeader>
        <div className="max-h-72 space-y-2 overflow-y-auto pe-1">
          {rateableSegments.map((segment, index) => (
            <div
              className="rounded-xl border border-border/60 bg-background/40 p-3"
              key={segment.id}
            >
              <div className="flex items-start gap-2">
                <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-muted font-medium tabular-nums text-[10px] text-muted-foreground">
                  {index + 1}
                </span>
                <p className="min-w-0 flex-1 text-pretty text-xs leading-5">
                  {segment.text}
                </p>
              </div>
              <div className="mt-2 flex items-center justify-end gap-1">
                <Button
                  aria-label={`Helpful sentence ${index + 1}`}
                  className={cn(
                    "h-7 rounded-full px-2.5 text-xs transition-[transform,background-color,color] duration-150 active:scale-[0.96]",
                    segment.rating === "up" &&
                      "bg-emerald-500/12 text-emerald-700 hover:bg-emerald-500/18 dark:text-emerald-300",
                  )}
                  data-icon="inline-start"
                  disabled={pendingTraceId === segment.id}
                  onClick={() => void handleFeedback(segment.id, "up")}
                  size="xs"
                  type="button"
                  variant={segment.rating === "up" ? "secondary" : "ghost"}
                >
                  <HugeiconsIcon
                    icon={HugeThumbsUpIcon}
                    className="size-3.5"
                    strokeWidth={1.8}
                  />
                  Helpful
                </Button>
                <Button
                  aria-label={`Off target sentence ${index + 1}`}
                  className={cn(
                    "h-7 rounded-full px-2.5 text-xs transition-[transform,background-color,color] duration-150 active:scale-[0.96]",
                    segment.rating === "down" &&
                      "bg-rose-500/12 text-rose-700 hover:bg-rose-500/18 dark:text-rose-300",
                  )}
                  data-icon="inline-start"
                  disabled={pendingTraceId === segment.id}
                  onClick={() => void handleFeedback(segment.id, "down")}
                  size="xs"
                  type="button"
                  variant={segment.rating === "down" ? "secondary" : "ghost"}
                >
                  <HugeiconsIcon
                    icon={HugeThumbsDownIcon}
                    className="size-3.5"
                    strokeWidth={1.8}
                  />
                  Off target
                </Button>
              </div>
            </div>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
};

const stepIcon = (text: string) => {
  const lower = text.toLowerCase();
  if (lower.includes("routing")) return <HugeiconsIcon icon={Route01Icon} />;
  if (lower.includes("retriev") || lower.includes("search")) {
    return <HugeiconsIcon icon={Search01Icon} />;
  }
  if (lower.includes("rerank")) {
    return <HugeiconsIcon icon={Sorting01Icon} />;
  }
  if (lower.includes("fus") || lower.includes("filter")) {
    return <HugeiconsIcon icon={Layers01Icon} />;
  }
  if (lower.includes("generat")) {
    return <HugeiconsIcon icon={HugeSparklesIcon} />;
  }
  return <HugeiconsIcon icon={Flowchart02Icon} />;
};

const RetrievalCandidate: FC<{
  candidate: {
    document_title: string;
    evidence_id: string;
    page: number;
    snippet: string;
  };
}> = ({ candidate }) => (
  <Collapsible>
    <CollapsibleTrigger
      render={
        <Badge variant="secondary">
          {`${candidate.document_title} · p.${candidate.page}`}
        </Badge>
      }
    />
    <CollapsibleContent className="mt-1 max-w-prose text-muted-foreground text-xs">
      {candidate.snippet}
    </CollapsibleContent>
  </Collapsible>
);

function getReasoningEntryKey(entry: ReasoningTraceEntry): string {
  if (entry.type === "step") {
    return `step-${entry.text ?? ""}`;
  }
  if (entry.type === "hop") {
    return `hop-${entry.hop ?? ""}-${entry.sub_query ?? ""}`;
  }
  const candidates = (entry.candidates ?? [])
    .map((candidate: RetrievalCandidateEntry) => candidate.evidence_id)
    .join("-");
  return `retrieval-${entry.label ?? ""}-${candidates}`;
}

const AssistantMessage: FC = () => {
  const {
    ToolFallback: ToolFallbackComponent = ToolFallback,
    ToolGroup,
    ReasoningGroup,
  } = useContext(ThreadComponentsContext);

  // reserves space for action bar and compensates with `-mb` for consistent msg spacing
  // keeps hovered action bar from shifting layout (autohide doesn't support absolute positioning well)
  // for pt-[n] use -mb-[n + 6] & min-h-[n + 6] to preserve compensation
  const ACTION_BAR_PT = "pt-1.5";
  const ACTION_BAR_HEIGHT = `-mb-7.5 min-h-7.5 ${ACTION_BAR_PT}`;
  const metadata = useAuiState(
    (s) => s.message.metadata?.custom as MessageMetadataCustom | undefined,
  );
  const isRunning = useAuiState((s) => s.message.status?.type === "running");
  const route = metadata?.route;
  const subQueries = metadata?.subQueries ?? [];
  const hopProgress = metadata?.hopProgress ?? [];
  const reasoningTrace = metadata?.reasoningTrace ?? [];
  const generating = metadata?.generating ?? false;

  const [cotOpen, setCotOpen] = useState(false);
  useEffect(() => {
    if (isRunning && !generating) {
      setCotOpen(true);
    } else if (generating) {
      setCotOpen(false);
    }
  }, [isRunning, generating]);

  return (
    <MessagePrimitive.Root
      className="fade-in slide-in-from-bottom-1 relative animate-in duration-150"
      data-role="assistant"
      data-slot="aui_assistant-message-root"
    >
      <div
        // [contain-intrinsic-size:auto_24px] fixes issue #4104, don't change without checking for regressions
        className="wrap-break-word px-2 text-foreground leading-relaxed [contain-intrinsic-size:auto_24px] [content-visibility:auto]"
        data-slot="aui_assistant-message-content"
      >
        {route ? (
          <div className="mb-3 flex flex-col gap-2">
            <Badge
              className={cn(
                "fade-in slide-in-from-bottom-1 inline-flex w-fit animate-in gap-1.5 rounded-full px-2.5 py-1 font-medium text-[11px] duration-300",
                routeBadgeClassName(route),
              )}
              variant="secondary"
            >
              <HugeiconsIcon
                icon={routeIcon(route)}
                size={14}
                strokeWidth={1.8}
              />
              {formatRouteLabel(route)}
            </Badge>
          </div>
        ) : null}

        {reasoningTrace.length > 0 ? (
          <div className="mb-3">
            <ChainOfThought open={cotOpen} onOpenChange={setCotOpen}>
              <ChainOfThoughtHeader shimmer={isRunning && !generating}>
                Process trace
              </ChainOfThoughtHeader>
              <ChainOfThoughtContent>
                {reasoningTrace.map((entry, index) => {
                  if (entry.type === "step") {
                    return (
                      <ChainOfThoughtStep
                        key={getReasoningEntryKey(entry)}
                        icon={stepIcon(entry.text ?? "")}
                        index={index}
                        label={formatTraceLabel(entry.text ?? "")}
                      />
                    );
                  }
                  if (entry.type === "hop") {
                    return (
                      <ChainOfThoughtStep
                        key={getReasoningEntryKey(entry)}
                        icon={<HugeiconsIcon icon={HugeGitBranchIcon} />}
                        index={index}
                        label={`Step ${entry.hop}`}
                        description={
                          <>
                            <div>{entry.sub_query}</div>
                            {entry.intermediate_answer ? (
                              <div>{entry.intermediate_answer}</div>
                            ) : null}
                          </>
                        }
                      />
                    );
                  }
                  return (
                    <ChainOfThoughtStep
                      key={getReasoningEntryKey(entry)}
                      icon={<HugeiconsIcon icon={Search01Icon} />}
                      index={index}
                      label={entry.label ?? "Retrieval"}
                    >
                      <ChainOfThoughtSearchResults>
                        {(entry.candidates ?? []).map((candidate) => (
                          <RetrievalCandidate
                            key={candidate.evidence_id}
                            candidate={candidate}
                          />
                        ))}
                      </ChainOfThoughtSearchResults>
                    </ChainOfThoughtStep>
                  );
                })}
              </ChainOfThoughtContent>
            </ChainOfThought>
          </div>
        ) : null}

        {route === "multi_hop" &&
        (subQueries.length > 0 || hopProgress.length > 0) ? (
          <div className="mb-3">
            <Accordion
              className="w-full max-w-2xl"
              defaultValue={["multi-hop-details"]}
              multiple
            >
              <AccordionItem value="multi-hop-details">
                <AccordionTrigger className="group flex w-fit items-center gap-2 rounded-lg px-1.5 py-1 font-medium text-muted-foreground text-xs transition-colors hover:bg-muted/40 hover:text-foreground">
                  <HugeiconsIcon
                    className="size-3.5"
                    icon={HugeGitBranchIcon}
                    strokeWidth={1.8}
                  />
                  <span>Multi-hop path</span>
                  <span className="rounded-full bg-muted px-1.5 py-0.5 font-mono text-[10px] tabular-nums">
                    {Math.max(subQueries.length, hopProgress.length)} steps
                  </span>
                </AccordionTrigger>
                <AccordionContent className="pt-1">
                  <div className="ml-2.5 border-border/70 border-s ps-4">
                    {Array.from({
                      length: Math.max(subQueries.length, hopProgress.length),
                    }).map((_, index) => {
                      const progress = hopProgress.find(
                        (hop) => hop.hop === index + 1,
                      );
                      const subQuery = subQueries[index] ?? progress?.sub_query;
                      const hopNumber = progress?.hop ?? index + 1;
                      const key = progress
                        ? `hop-${progress.hop}`
                        : subQuery
                          ? `query-${subQuery}`
                          : `hop-${hopNumber}`;

                      return (
                        <div
                          className="relative space-y-1 pb-4 last:pb-1"
                          key={key}
                        >
                          <span className="absolute left-[-1.3rem] top-0.5 flex size-4 items-center justify-center rounded-full border border-border bg-background font-mono text-[9px] text-muted-foreground">
                            {hopNumber}
                          </span>
                          <p className="text-xs leading-5 text-foreground">
                            {subQuery ?? "Retrieving the next evidence set"}
                          </p>
                          {progress?.intermediate_answer ? (
                            <MarkdownText
                              className="text-muted-foreground text-xs leading-5"
                              content={progress.intermediate_answer}
                            />
                          ) : null}
                        </div>
                      );
                    })}
                  </div>
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </div>
        ) : null}

        <MessagePrimitive.GroupedParts
          groupBy={groupPartByType({
            reasoning: ["group-chainOfThought", "group-reasoning"],
            "tool-call": ["group-chainOfThought", "group-tool"],
            "standalone-tool-call": [],
          })}
        >
          {({ part, children }) => {
            switch (part.type) {
              case "group-chainOfThought":
                return <div data-slot="aui_chain-of-thought">{children}</div>;
              case "group-tool":
                if (ToolGroup) {
                  return <ToolGroup group={part}>{children}</ToolGroup>;
                }
                return (
                  <ToolGroupRoot variant="ghost">
                    <ToolGroupTrigger
                      active={part.status.type === "running"}
                      count={part.indices.length}
                    />
                    <ToolGroupContent>{children}</ToolGroupContent>
                  </ToolGroupRoot>
                );
              case "group-reasoning": {
                if (ReasoningGroup) {
                  return (
                    <ReasoningGroup group={part}>{children}</ReasoningGroup>
                  );
                }
                return null;
              }
              case "text":
                return <TextWithCitations />;
              case "image":
                return (
                  <figure className="my-3 max-w-2xl overflow-hidden rounded-xl border bg-muted/20">
                    <img
                      alt={part.filename ?? "Retrieved document image"}
                      className="h-auto max-h-[32rem] w-full object-contain"
                      loading="lazy"
                      src={part.image}
                    />
                    {part.filename ? (
                      <figcaption className="border-t px-3 py-2 text-muted-foreground text-xs">
                        {part.filename}
                      </figcaption>
                    ) : null}
                  </figure>
                );
              case "reasoning":
                return null;
              case "tool-call":
                return part.toolUI ?? <ToolFallbackComponent {...part} />;
              case "data":
                return part.dataRendererUI;
              case "source":
                return <Sources {...part} />;
              case "indicator":
                return (
                  <span
                    aria-label="Assistant is working"
                    className="animate-pulse font-sans"
                    data-slot="aui_assistant-message-indicator"
                    role="status"
                  >
                    {"●"}
                  </span>
                );
              default:
                return null;
            }
          }}
        </MessagePrimitive.GroupedParts>
        <MessageError />
      </div>

      <div
        className={cn("ms-2 flex items-center gap-0.5", ACTION_BAR_HEIGHT)}
        data-slot="aui_assistant-message-footer"
      >
        <AssistantActionBar />
      </div>
    </MessagePrimitive.Root>
  );
};

const AssistantActionBar: FC = () => (
  <ActionBarPrimitive.Root
    autohide="never"
    className="aui-assistant-action-bar-root fade-in col-start-3 row-start-2 -ms-1 flex animate-in gap-1 text-muted-foreground duration-200"
    hideWhenRunning
  >
    <ActionBarPrimitive.Copy asChild>
      <TooltipIconButton tooltip="Copy">
        <AuiIf condition={(s) => s.message.isCopied}>
          <HugeiconsIcon
            className="zoom-in-50 fade-in animate-in duration-200 ease-out"
            icon={CopyCheckIcon}
          />
        </AuiIf>
        <AuiIf condition={(s) => !s.message.isCopied}>
          <HugeiconsIcon
            className="zoom-in-75 fade-in animate-in duration-150"
            icon={Copy01Icon}
          />
        </AuiIf>
      </TooltipIconButton>
    </ActionBarPrimitive.Copy>
    <SentenceFeedbackPopover />
    <ActionBarPrimitive.Reload asChild>
      <TooltipIconButton tooltip="Regenerate">
        <HugeiconsIcon icon={Refresh01Icon} />
      </TooltipIconButton>
    </ActionBarPrimitive.Reload>
    <ActionBarMorePrimitive.Root>
      <ActionBarMorePrimitive.Trigger asChild>
        <TooltipIconButton
          className="data-[state=open]:bg-accent"
          tooltip="More"
        >
          <HugeiconsIcon icon={HugeMoreHorizontalIcon} />
        </TooltipIconButton>
      </ActionBarMorePrimitive.Trigger>
      <ActionBarMorePrimitive.Content
        align="start"
        className="aui-action-bar-more-content data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2 z-50 min-w-32 overflow-hidden rounded-xl border bg-popover/95 p-1.5 text-popover-foreground shadow-lg backdrop-blur-sm data-[state=closed]:animate-out data-[state=open]:animate-in"
        side="bottom"
        sideOffset={6}
      >
        <ActionBarPrimitive.ExportMarkdown asChild>
          <ActionBarMorePrimitive.Item className="aui-action-bar-more-item flex cursor-pointer select-none items-center gap-2 rounded-lg px-2.5 py-1.5 text-sm outline-none hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground">
            <HugeiconsIcon className="size-4" icon={Download01Icon} />
            Export as Markdown
          </ActionBarMorePrimitive.Item>
        </ActionBarPrimitive.ExportMarkdown>
      </ActionBarMorePrimitive.Content>
    </ActionBarMorePrimitive.Root>
  </ActionBarPrimitive.Root>
);

const UserMessage: FC = () => (
  <MessagePrimitive.Root
    className="fade-in slide-in-from-bottom-1 grid animate-in auto-rows-auto grid-cols-[minmax(72px,1fr)_auto] content-start gap-y-2 px-2 duration-150 [contain-intrinsic-size:auto_60px] [content-visibility:auto] [&:where(>*)]:col-start-2"
    data-role="user"
    data-slot="aui_user-message-root"
  >
    <UserMessageAttachments />

    <div className="aui-user-message-content-wrapper relative col-start-2 min-w-0">
      <div className="aui-user-message-content peer wrap-break-word rounded-xl bg-muted px-4 py-2 text-foreground empty:hidden">
        <MessagePrimitive.Parts />
      </div>
      <div className="aui-user-action-bar-wrapper absolute inset-s-0 top-1/2 -translate-x-full -translate-y-1/2 pe-2 peer-empty:hidden rtl:translate-x-full">
        <UserActionBar />
      </div>
    </div>
  </MessagePrimitive.Root>
);

const UserActionBar: FC = () => (
  <ActionBarPrimitive.Root
    autohide="not-last"
    className="aui-user-action-bar-root flex flex-col items-end"
    hideWhenRunning
  >
    <ActionBarPrimitive.Edit asChild>
      <TooltipIconButton className="aui-user-action-edit" tooltip="Edit">
        <PencilIcon />
      </TooltipIconButton>
    </ActionBarPrimitive.Edit>
  </ActionBarPrimitive.Root>
);

const EditComposer: FC = () => (
  <MessagePrimitive.Root
    className="flex flex-col px-2"
    data-slot="aui_edit-composer-wrapper"
  >
    <ComposerPrimitive.Root className="aui-edit-composer-root ms-auto flex w-full max-w-[85%] flex-col rounded-(--composer-radius) border border-border/60 bg-(--composer-bg) shadow-[0_4px_16px_-8px_rgba(0,0,0,0.08),0_1px_2px_rgba(0,0,0,0.04)] dark:border-muted-foreground/15 dark:shadow-none">
      <ComposerPrimitive.Input
        autoFocus
        className="aui-edit-composer-input min-h-14 w-full resize-none bg-transparent px-4 pt-3 pb-1 text-base text-foreground outline-none"
      />
      <div className="aui-edit-composer-footer mx-2.5 mb-2.5 flex items-center gap-1.5 self-end">
        <ComposerPrimitive.Cancel asChild>
          <Button className="h-8 rounded-full px-3.5" size="sm" variant="ghost">
            Cancel
          </Button>
        </ComposerPrimitive.Cancel>
        <ComposerPrimitive.Send asChild>
          <Button className="h-8 rounded-full px-3.5" size="sm">
            Update
          </Button>
        </ComposerPrimitive.Send>
      </div>
    </ComposerPrimitive.Root>
  </MessagePrimitive.Root>
);
