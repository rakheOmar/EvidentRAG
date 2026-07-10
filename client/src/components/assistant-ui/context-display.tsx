"use client";

import { useAuiState } from "@assistant-ui/react";
import type { ThreadTokenUsage } from "@assistant-ui/react-ai-sdk";
import { useThreadTokenUsage } from "@assistant-ui/react-ai-sdk";
import {
  createContext,
  type FC,
  type ReactNode,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { ContextUsage } from "@/lib/types";
import { cn } from "@/lib/utils";

const formatTokenCount = (tokens: number): string => {
  if (tokens >= 1_000_000) {
    return `${(tokens / 1_000_000).toFixed(1)}M`;
  }
  if (tokens >= 1000) {
    return `${(tokens / 1000).toFixed(1)}k`;
  }
  return `${tokens}`;
};

const getUsagePercent = (
  totalTokens: number | undefined,
  modelContextWindow: number,
): number => {
  if (!totalTokens) {
    return 0;
  }
  return Math.min((totalTokens / modelContextWindow) * 100, 100);
};

type UsageSeverity = "normal" | "warning" | "critical";

const getUsageSeverity = (percent: number): UsageSeverity => {
  if (percent > 85) {
    return "critical";
  }
  if (percent >= 65) {
    return "warning";
  }
  return "normal";
};

const getStrokeColor = (percent: number): string => {
  const severity = getUsageSeverity(percent);
  if (severity === "critical") {
    return "stroke-red-500";
  }
  if (severity === "warning") {
    return "stroke-amber-500";
  }
  return "stroke-emerald-500";
};

const getBarColor = (percent: number): string => {
  const severity = getUsageSeverity(percent);
  if (severity === "critical") {
    return "bg-red-500";
  }
  if (severity === "warning") {
    return "bg-amber-500";
  }
  return "bg-emerald-500";
};

function useServerThreadUsage():
  { estimated: boolean; usage: ThreadTokenUsage } | undefined {
  const messages = useAuiState((s) => s.thread.messages);

  return useMemo(() => {
    for (const message of [...messages].reverse()) {
      const custom = message.metadata?.custom;
      const contextUsage =
        typeof custom === "object" &&
        custom !== null &&
        "contextUsage" in custom
          ? custom.contextUsage
          : undefined;
      if (!contextUsage || typeof contextUsage !== "object") {
        continue;
      }
      const usage = contextUsage as ContextUsage;
      return {
        estimated: usage.estimated,
        usage: {
          inputTokens: usage.prompt_tokens,
          outputTokens: usage.completion_tokens,
          totalTokens: usage.total_tokens,
        },
      };
    }
    return undefined;
  }, [messages]);
}

type ContextDisplayContextValue = {
  estimated: boolean;
  usage: ThreadTokenUsage | undefined;
  totalTokens: number;
  percent: number;
  modelContextWindow: number;
};

const ContextDisplayContext = createContext<ContextDisplayContextValue | null>(
  null,
);

function useContextDisplay(): ContextDisplayContextValue {
  const ctx = useContext(ContextDisplayContext);
  if (!ctx) {
    throw new Error("ContextDisplay.* must be used within ContextDisplay.Root");
  }
  return ctx;
}

type PresetProps = {
  modelContextWindow: number;
  className?: string;
  side?: "top" | "bottom" | "left" | "right";
  usage?: ThreadTokenUsage | undefined;
};

type ContextDisplayRootProps = {
  modelContextWindow: number;
  children: ReactNode;
  usage?: ThreadTokenUsage | undefined;
};

function ContextDisplayRootBase({
  modelContextWindow,
  children,
  usage,
  estimated,
}: {
  modelContextWindow: number;
  children: ReactNode;
  usage: ThreadTokenUsage | undefined;
  estimated: boolean;
}) {
  const threadId = useAuiState((s) => s.threadListItem.id);
  const rawTokens = usage?.totalTokens ?? 0;
  const [tokenState, setTokenState] = useState({
    threadId,
    totalTokens: rawTokens > 0 ? rawTokens : 0,
    usage,
  });

  useEffect(() => {
    setTokenState((prev) => {
      if (prev.threadId !== threadId) {
        return {
          threadId,
          totalTokens: rawTokens > 0 ? rawTokens : 0,
          usage,
        };
      }
      if (rawTokens > 0 && rawTokens !== prev.totalTokens) {
        return { ...prev, totalTokens: rawTokens, usage };
      }
      if (usage !== prev.usage) {
        return { ...prev, usage };
      }
      return prev;
    });
  }, [threadId, rawTokens, usage]);

  const totalTokens = tokenState.totalTokens;
  const percent = getUsagePercent(totalTokens, modelContextWindow);

  const contextValue = useMemo(
    () => ({
      usage: tokenState.usage,
      estimated,
      totalTokens,
      percent,
      modelContextWindow,
    }),
    [estimated, tokenState.usage, totalTokens, percent, modelContextWindow],
  );

  return (
    <ContextDisplayContext.Provider value={contextValue}>
      <Tooltip>{children}</Tooltip>
    </ContextDisplayContext.Provider>
  );
}

function ContextDisplayRootInternal({
  modelContextWindow,
  children,
}: {
  modelContextWindow: number;
  children: ReactNode;
}) {
  const runtimeUsage = useThreadTokenUsage();
  const serverUsage = useServerThreadUsage();
  return (
    <ContextDisplayRootBase
      modelContextWindow={modelContextWindow}
      usage={runtimeUsage ?? serverUsage?.usage}
      estimated={
        runtimeUsage === undefined && (serverUsage?.estimated ?? false)
      }
    >
      {children}
    </ContextDisplayRootBase>
  );
}

function ContextDisplayRoot(props: ContextDisplayRootProps) {
  if (props.usage !== undefined) {
    return (
      <ContextDisplayRootBase
        modelContextWindow={props.modelContextWindow}
        usage={props.usage}
        estimated={false}
      >
        {props.children}
      </ContextDisplayRootBase>
    );
  }
  return (
    <ContextDisplayRootInternal modelContextWindow={props.modelContextWindow}>
      {props.children}
    </ContextDisplayRootInternal>
  );
}

function ContextDisplayTrigger({
  className,
  children,
  ...props
}: React.ComponentProps<"button">) {
  return (
    <TooltipTrigger
      render={
        <button
          className={cn(
            "inline-flex items-center rounded-md transition-colors",
            className,
          )}
          data-slot="context-display-trigger"
          type="button"
          {...props}
        >
          {children}
        </button>
      }
    />
  );
}

function ContextDisplayContent({
  side = "top",
  className,
}: {
  side?: "top" | "bottom" | "left" | "right" | undefined;
  className?: string;
}) {
  const { estimated, usage, totalTokens, percent, modelContextWindow } =
    useContextDisplay();

  return (
    <TooltipContent
      className={cn(
        "[&_span>svg]:hidden! rounded-lg border bg-popover px-3 py-2 text-popover-foreground shadow-md",
        className,
      )}
      data-slot="context-display-popover"
      side={side}
      sideOffset={8}
    >
      <div className="grid min-w-40 gap-1.5 text-xs">
        <div className="flex items-center justify-between gap-4">
          <span className="text-muted-foreground">
            {estimated ? "Estimated usage" : usage ? "Usage" : "Usage status"}
          </span>
          <span className="font-mono tabular-nums">
            {usage ? `${Math.round(percent)}%` : "Unavailable"}
          </span>
        </div>
        {!usage && (
          <p className="text-muted-foreground text-[11px] leading-4">
            Tracking starts with new responses.
          </p>
        )}
        {usage?.inputTokens !== undefined && (
          <div className="flex items-center justify-between gap-4">
            <span className="text-muted-foreground">Input</span>
            <span className="font-mono tabular-nums">
              {formatTokenCount(usage.inputTokens)}
            </span>
          </div>
        )}
        {usage?.cachedInputTokens !== undefined &&
          usage.cachedInputTokens > 0 && (
            <div className="flex items-center justify-between gap-4">
              <span className="text-muted-foreground">Cached</span>
              <span className="font-mono tabular-nums">
                {formatTokenCount(usage.cachedInputTokens)}
              </span>
            </div>
          )}
        {usage?.outputTokens !== undefined && (
          <div className="flex items-center justify-between gap-4">
            <span className="text-muted-foreground">Output</span>
            <span className="font-mono tabular-nums">
              {formatTokenCount(usage.outputTokens)}
            </span>
          </div>
        )}
        {usage?.reasoningTokens !== undefined && usage.reasoningTokens > 0 && (
          <div className="flex items-center justify-between gap-4">
            <span className="text-muted-foreground">Reasoning</span>
            <span className="font-mono tabular-nums">
              {formatTokenCount(usage.reasoningTokens)}
            </span>
          </div>
        )}
        <div className="mt-0.5 border-t pt-1.5">
          <div className="flex items-center justify-between gap-4">
            <span className="text-muted-foreground">Total</span>
            <span className="font-mono tabular-nums">
              {formatTokenCount(totalTokens)} /{" "}
              {formatTokenCount(modelContextWindow)}
            </span>
          </div>
        </div>
      </div>
    </TooltipContent>
  );
}

const RING_SIZE = 24;
const RING_STROKE = 3;
const RING_RADIUS = (RING_SIZE - RING_STROKE) / 2;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;

function RingVisual() {
  const { percent } = useContextDisplay();

  return (
    <svg
      aria-hidden="true"
      className="-rotate-90"
      height={RING_SIZE}
      viewBox={`0 0 ${RING_SIZE} ${RING_SIZE}`}
      width={RING_SIZE}
    >
      <circle
        className="stroke-muted"
        cx={RING_SIZE / 2}
        cy={RING_SIZE / 2}
        fill="none"
        r={RING_RADIUS}
        strokeWidth={RING_STROKE}
      />
      <circle
        className={cn(
          "transition-[stroke-dashoffset,stroke] duration-300",
          getStrokeColor(percent),
        )}
        cx={RING_SIZE / 2}
        cy={RING_SIZE / 2}
        fill="none"
        r={RING_RADIUS}
        strokeDasharray={RING_CIRCUMFERENCE}
        strokeDashoffset={
          RING_CIRCUMFERENCE - (percent / 100) * RING_CIRCUMFERENCE
        }
        strokeLinecap="round"
        strokeWidth={RING_STROKE}
      />
    </svg>
  );
}

function RingTrigger() {
  const { estimated, usage } = useContextDisplay();
  return (
    <ContextDisplayTrigger
      aria-label={
        estimated
          ? "Estimated context usage"
          : usage
            ? "Context usage"
            : "Context usage unavailable"
      }
      className="p-1"
    >
      <RingVisual />
    </ContextDisplayTrigger>
  );
}

const ContextDisplayRing: FC<PresetProps> = ({
  modelContextWindow,
  className,
  side,
  usage,
}) => (
  <ContextDisplayRoot modelContextWindow={modelContextWindow} usage={usage}>
    <div className={className}>
      <RingTrigger />
    </div>
    <ContextDisplayContent side={side} />
  </ContextDisplayRoot>
);

function BarVisual() {
  const { percent, totalTokens } = useContextDisplay();

  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-muted">
        <div
          className={cn(
            "h-full rounded-full transition-all duration-300",
            getBarColor(percent),
          )}
          style={{ width: `${percent}%` }}
        />
      </div>
      <span className="text-[10px] text-muted-foreground tabular-nums">
        {formatTokenCount(totalTokens)} ({Math.round(percent)}%)
      </span>
    </div>
  );
}

const ContextDisplayBar: FC<PresetProps> = ({
  modelContextWindow,
  className,
  side,
  usage,
}) => (
  <ContextDisplayRoot modelContextWindow={modelContextWindow} usage={usage}>
    <ContextDisplayTrigger
      aria-label="Context usage"
      className={cn("px-2 py-1", className)}
    >
      <BarVisual />
    </ContextDisplayTrigger>
    <ContextDisplayContent side={side} />
  </ContextDisplayRoot>
);

function TextVisual() {
  const { totalTokens, modelContextWindow } = useContextDisplay();

  return (
    <>
      {formatTokenCount(totalTokens)} / {formatTokenCount(modelContextWindow)}
    </>
  );
}

const ContextDisplayText: FC<PresetProps> = ({
  modelContextWindow,
  className,
  side,
  usage,
}) => (
  <ContextDisplayRoot modelContextWindow={modelContextWindow} usage={usage}>
    <ContextDisplayTrigger
      aria-label="Context usage"
      className={cn(
        "px-2 py-1 font-mono text-muted-foreground text-xs tabular-nums hover:bg-accent hover:text-accent-foreground",
        className,
      )}
    >
      <TextVisual />
    </ContextDisplayTrigger>
    <ContextDisplayContent side={side} />
  </ContextDisplayRoot>
);

const ContextDisplay = {} as {
  Root: typeof ContextDisplayRoot;
  Trigger: typeof ContextDisplayTrigger;
  Content: typeof ContextDisplayContent;
  Ring: typeof ContextDisplayRing;
  Bar: typeof ContextDisplayBar;
  Text: typeof ContextDisplayText;
};

ContextDisplay.Root = ContextDisplayRoot;
ContextDisplay.Trigger = ContextDisplayTrigger;
ContextDisplay.Content = ContextDisplayContent;
ContextDisplay.Ring = ContextDisplayRing;
ContextDisplay.Bar = ContextDisplayBar;
ContextDisplay.Text = ContextDisplayText;

export {
  ContextDisplay,
  ContextDisplayBar,
  ContextDisplayContent,
  ContextDisplayRing,
  ContextDisplayRoot,
  ContextDisplayText,
  ContextDisplayTrigger,
};
