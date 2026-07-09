"use client";

import {
  ActionBarMorePrimitive,
  ActionBarPrimitive,
  type AssistantState,
  AuiIf,
  BranchPickerPrimitive,
  ComposerPrimitive,
  ErrorPrimitive,
  groupPartByType,
  MessagePrimitive,
  SuggestionPrimitive,
  ThreadPrimitive,
  type ToolCallMessagePartComponent,
  useAuiState,
} from "@assistant-ui/react";
import type { QueryRoute } from "@/lib/types";
import {
  ArrowDownIcon,
  ArrowUpIcon,
  CheckIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  CopyIcon,
  DownloadIcon,
  DotIcon,
  GitBranchIcon,
  LayersIcon,
  MicIcon,
  MoreHorizontalIcon,
  PencilIcon,
  RefreshCwIcon,
  RouteIcon,
  SearchIcon,
  SparklesIcon,
  SquareIcon,
  ThumbsDownIcon,
  ThumbsUpIcon,
} from "lucide-react";
import {
  type ComponentType,
  createContext,
  type FC,
  type PropsWithChildren,
  useCallback,
  useEffect,
  useContext,
  useMemo,
  useState,
} from "react";
import {
  ComposerAddAttachment,
  ComposerAttachments,
  UserMessageAttachments,
} from "@/components/assistant-ui/attachment";
import { InlineCitationText } from "@/components/assistant-ui/inline-citations";
import { MarkdownText } from "@/components/assistant-ui/markdown-text";
import { Sources } from "@/components/assistant-ui/sources";
import {
  ChainOfThought,
  ChainOfThoughtContent,
  ChainOfThoughtHeader,
  ChainOfThoughtSearchResults,
  ChainOfThoughtStep,
} from "@/components/assistant-ui/chain-of-thought";
import { ToolFallback } from "@/components/assistant-ui/tool-fallback";
import {
  ToolGroupContent,
  ToolGroupRoot,
  ToolGroupTrigger,
} from "@/components/assistant-ui/tool-group";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
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
import { useEvidencePanel } from "@/components/chat/evidence-context";
import { putSentenceTraceFeedback } from "@/lib/api";
import { getMessageSegments, updateSegmentRating } from "@/lib/segments-store";
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

type ReasoningTraceEntry =
  NonNullable<MessageMetadataCustom["reasoningTrace"]>[number];

type RetrievalCandidateEntry = NonNullable<ReasoningTraceEntry["candidates"]>[number];

function formatRouteLabel(route: QueryRoute): string {
  switch (route) {
    case "multi_hop":
      return "Multi-hop";
    case "comparison":
      return "Comparison";
    case "aggregation":
      return "Aggregation";
    case "conversation":
      return "Conversation";
    default:
      return "Simple";
  }
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
    | ComponentType<PropsWithChildren<{ group: ThreadGroupPart }>>
    | undefined;
  ReasoningGroup?:
    | ComponentType<PropsWithChildren<{ group: ThreadGroupPart }>>
    | undefined;
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
            isEmpty && "justify-center"
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
                "sticky bottom-0 mt-auto rounded-t-(--composer-radius)"
            )}
          >
            <ThreadScrollToBottom />
            <Composer />
            <AuiIf condition={(s) => isNewChatView(s) && s.composer.isEmpty}>
              <ThreadSuggestions />
            </AuiIf>
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
          className="aui-composer-input max-h-32 min-h-10 w-full resize-none bg-transparent px-2.5 py-1 text-base outline-none placeholder:text-muted-foreground/80"
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
  const [pendingTraceId, setPendingTraceId] = useState<string | null>(null);
  const { selectedEvidenceIds, selectEvidence, clearEvidence } =
    useEvidencePanel();

  const selectedEvidenceSet = useMemo(
    () => new Set(selectedEvidenceIds),
    [selectedEvidenceIds]
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
      const previousText = index > 0 ? segments[index - 1]?.text ?? "" : "";
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
    [messageId]
  );

  if (segments && segments.length > 0) {
    return (
      <>
        {renderedSegments.map((seg) => {
          const isHighlighted =
            seg.evidence_ids.length > 0 &&
            (hoveredId !== null
              ? seg.evidence_ids.includes(hoveredId)
              : seg.evidence_ids.some((id) => selectedEvidenceSet.has(id)));

          return (
            <span className="inline-flex items-center gap-1" key={seg.segment_index}>
              <InlineCitationText
                className={
                  isHighlighted ? "rounded bg-accent/80 shadow-sm" : undefined
                }
              >
                {seg.text}
              </InlineCitationText>
              {seg.evidence_ids.length > 0 ? (
                <span className="inline-flex items-center gap-0.5 align-baseline">
                  <Button
                    aria-label="Thumbs up this sentence"
                    className={cn(
                      "size-5 rounded-full p-0",
                      seg.rating === "up" && "bg-emerald-500/15 text-emerald-700"
                    )}
                    disabled={pendingTraceId === seg.id}
                    onClick={() => void handleFeedback(seg.id, "up")}
                    size="icon"
                    type="button"
                    variant="ghost"
                  >
                    <ThumbsUpIcon className="size-3" />
                  </Button>
                  <Button
                    aria-label="Thumbs down this sentence"
                    className={cn(
                      "size-5 rounded-full p-0",
                      seg.rating === "down" && "bg-rose-500/15 text-rose-700"
                    )}
                    disabled={pendingTraceId === seg.id}
                    onClick={() => void handleFeedback(seg.id, "down")}
                    size="icon"
                    type="button"
                    variant="ghost"
                  >
                    <ThumbsDownIcon className="size-3" />
                  </Button>
                </span>
              ) : null}
            </span>
          );
        })}
        {evidenceNumbers.size > 0 && (
          <span className="ms-1 inline-flex items-center gap-0.5 align-baseline">
            {[...evidenceNumbers.entries()].map(([id, num]) => {
              const isSelected = selectedEvidenceSet.has(id);
              return (
                <Badge
                  key={id}
                  variant={isSelected ? "default" : "secondary"}
                  className="ml-0.5 rounded-full cursor-pointer"
                  onMouseEnter={() => setHoveredId(id)}
                  onMouseLeave={() => setHoveredId(null)}
                  onClick={() => {
                    if (
                      selectedEvidenceIds.length === 1 &&
                      selectedEvidenceIds[0] === id
                    ) {
                      clearEvidence();
                    } else {
                      selectEvidence(messageId, [id]);
                    }
                  }}
                >
                  {num}
                </Badge>
              );
            })}
          </span>
        )}
      </>
    );
  }

  return <MarkdownText />;
};

const stepIcon = (text: string) => {
  const lower = text.toLowerCase();
  if (lower.includes("routing")) return RouteIcon;
  if (lower.includes("retriev") || lower.includes("search"))
    return SearchIcon;
  if (lower.includes("fus") || lower.includes("rerank") || lower.includes("filter"))
    return LayersIcon;
  if (lower.includes("generat")) return SparklesIcon;
  return DotIcon;
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

function getReasoningEntryKey(
  entry: ReasoningTraceEntry
): string {
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
    (s) => s.message.metadata?.custom as MessageMetadataCustom | undefined
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
            <Badge className={routeBadgeClassName(route)} variant="secondary">
              {formatRouteLabel(route)}
            </Badge>

            {route === "multi_hop" && (subQueries.length > 0 || hopProgress.length > 0) ? (
              <Accordion className="w-full" defaultValue={["multi-hop-details"]} multiple>
                <AccordionItem value="multi-hop-details">
                  <AccordionTrigger className="py-1 font-medium text-muted-foreground text-xs">
                    Multi-hop steps
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="space-y-3 rounded-xl border border-border/60 bg-muted/30 p-3">
                      {subQueries.map((subQuery, index) => {
                        const progress = hopProgress.find((hop) => hop.hop === index + 1);

                        return (
                          <div key={subQuery} className="space-y-1">
                            <p className="font-medium text-[11px] uppercase tracking-wide text-muted-foreground">
                              Step {index + 1}
                            </p>
                            <p className="text-sm">{subQuery}</p>
                            {progress?.intermediate_answer ? (
                              <p className="text-muted-foreground text-sm">
                                {progress.intermediate_answer}
                              </p>
                            ) : null}
                          </div>
                        );
                      })}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            ) : null}
          </div>
        ) : null}

        {reasoningTrace.length > 0 ? (
          <div className="mb-3">
            <ChainOfThought open={cotOpen} onOpenChange={setCotOpen}>
              <ChainOfThoughtHeader shimmer={isRunning && !generating}>Process trace</ChainOfThoughtHeader>
              <ChainOfThoughtContent>
                {reasoningTrace.map((entry) => {
                  if (entry.type === "step") {
                    return (
                      <ChainOfThoughtStep
                        key={getReasoningEntryKey(entry)}
                        icon={stepIcon(entry.text ?? "")}
                        label={entry.text ?? ""}
                      />
                    );
                  }
                  if (entry.type === "hop") {
                    return (
                      <ChainOfThoughtStep
                        key={getReasoningEntryKey(entry)}
                        icon={GitBranchIcon}
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
                      icon={SearchIcon}
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
        className={cn("ms-2 flex items-center", ACTION_BAR_HEIGHT)}
        data-slot="aui_assistant-message-footer"
      >
        <BranchPicker />
        <AssistantActionBar />
      </div>
    </MessagePrimitive.Root>
  );
};

const AssistantActionBar: FC = () => (
  <ActionBarPrimitive.Root
    autohide="not-last"
    className="aui-assistant-action-bar-root fade-in col-start-3 row-start-2 -ms-1 flex animate-in gap-1 text-muted-foreground duration-200"
    hideWhenRunning
  >
    <ActionBarPrimitive.Copy asChild>
      <TooltipIconButton tooltip="Copy">
        <AuiIf condition={(s) => s.message.isCopied}>
          <CheckIcon className="zoom-in-50 fade-in animate-in duration-200 ease-out" />
        </AuiIf>
        <AuiIf condition={(s) => !s.message.isCopied}>
          <CopyIcon className="zoom-in-75 fade-in animate-in duration-150" />
        </AuiIf>
      </TooltipIconButton>
    </ActionBarPrimitive.Copy>
    <ActionBarPrimitive.Reload asChild>
      <TooltipIconButton tooltip="Refresh">
        <RefreshCwIcon />
      </TooltipIconButton>
    </ActionBarPrimitive.Reload>
    <ActionBarMorePrimitive.Root>
      <ActionBarMorePrimitive.Trigger asChild>
        <TooltipIconButton
          className="data-[state=open]:bg-accent"
          tooltip="More"
        >
          <MoreHorizontalIcon />
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
            <DownloadIcon className="size-4" />
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

    <BranchPicker
      className="col-span-full col-start-1 row-start-3 -me-1 justify-end"
      data-slot="aui_user-branch-picker"
    />
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

const BranchPicker: FC<BranchPickerPrimitive.Root.Props> = ({
  className,
  ...rest
}) => (
  <BranchPickerPrimitive.Root
    className={cn(
      "aui-branch-picker-root -ms-2 me-2 inline-flex items-center text-muted-foreground text-xs",
      className
    )}
    hideWhenSingleBranch
    {...rest}
  >
    <BranchPickerPrimitive.Previous asChild>
      <TooltipIconButton tooltip="Previous">
        <ChevronLeftIcon />
      </TooltipIconButton>
    </BranchPickerPrimitive.Previous>
    <span className="aui-branch-picker-state font-medium">
      <BranchPickerPrimitive.Number /> / <BranchPickerPrimitive.Count />
    </span>
    <BranchPickerPrimitive.Next asChild>
      <TooltipIconButton tooltip="Next">
        <ChevronRightIcon />
      </TooltipIconButton>
    </BranchPickerPrimitive.Next>
  </BranchPickerPrimitive.Root>
);
