"use client";

import { MessagePrimitive, useAuiState } from "@assistant-ui/react";
import type { ReactNode } from "react";

import {
  ReasoningContent,
  ReasoningRoot,
  ReasoningText,
  ReasoningTrigger,
} from "@/components/assistant-ui/reasoning";
import { Badge } from "@/components/ui/badge";
import { buildEvidenceIndexMap } from "@/lib/evidence-utils";
import { cn } from "@/lib/utils";

import { useEvidenceSelection } from "./evidence-selection";
import { useEvidentMessages } from "./evident-messages";

function getRouteLabel(route: string | null | undefined) {
  if (route === "simple") {
    return "Simple Route";
  }

  return null;
}

function getStatusLabel(phase: string | undefined) {
  switch (phase) {
    case "routing": {
      return "Routing Query";
    }
    case "retrieving": {
      return "Retrieving Evidence";
    }
    case "generating": {
      return "Generating Answer";
    }
    default: {
      return null;
    }
  }
}

const EvidentAssistantMessage = () => {
  const messageId = useAuiState((s) => s.message.id);
  const { messages } = useEvidentMessages();
  const { selectEvidence, selectedEvidenceId } = useEvidenceSelection();

  const message = messages.find((entry) => entry.id === messageId);

  if (message === undefined) {
    return <MessagePrimitive.Parts />;
  }

  const messageContent =
    typeof message.content === "string" ? message.content : "";

  const routeLabel = getRouteLabel(message.route);
  const statusLabel = getStatusLabel(message.phase);
  const answerSentences = Array.isArray(message.answer?.sentences)
    ? message.answer.sentences
    : null;
  const evidenceIndexMap = buildEvidenceIndexMap(answerSentences ?? []);
  let messageBody: ReactNode;

  if (
    message.phase === "done" &&
    message.answer !== undefined &&
    message.answer !== null &&
    answerSentences !== null
  ) {
    messageBody = (
      <div className="flex flex-col gap-3 text-sm sm:text-base">
        {answerSentences.map((sentence) => (
          <p
            className="whitespace-pre-wrap leading-relaxed"
            key={sentence.sentence_index}
          >
            {sentence.sentence_text}{" "}
            {sentence.evidence_ids.map((evidenceId) => {
              const evidenceIndex = evidenceIndexMap.get(evidenceId);

              if (evidenceIndex === undefined) {
                return null;
              }

              return (
                <button
                  aria-label={`Open Evidence ${evidenceIndex}`}
                  className="inline-flex align-baseline"
                  key={evidenceId}
                  onClick={() => selectEvidence(evidenceId)}
                  type="button"
                >
                  <Badge
                    className={cn(
                      "ml-1 cursor-pointer align-super text-[0.65rem]",
                      selectedEvidenceId === evidenceId &&
                        "bg-primary text-primary-foreground"
                    )}
                    variant="secondary"
                  >
                    [{evidenceIndex}]
                  </Badge>
                </button>
              );
            })}
          </p>
        ))}
      </div>
    );
  } else if (messageContent.length > 0) {
    messageBody = (
      <div className="whitespace-pre-wrap text-sm leading-relaxed sm:text-base">
        {messageContent}
      </div>
    );
  } else {
    messageBody = (
      <div className="text-muted-foreground text-sm">
        Waiting for the Answer...
      </div>
    );
  }

  return (
    <MessagePrimitive.Root
      className="fade-in slide-in-from-bottom-1 relative animate-in duration-150"
      data-role="assistant"
    >
      <div className="flex flex-col gap-3 px-2 text-foreground leading-relaxed">
        <div className="flex items-center gap-2">
          {routeLabel === null ? null : (
            <Badge variant="outline">{routeLabel}</Badge>
          )}
          {statusLabel === null || message.phase === "done" ? null : (
            <Badge variant="secondary">{statusLabel}</Badge>
          )}
        </div>

        {message.phase === "error" ? (
          <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-destructive text-sm">
            {message.errorMessage ?? "The Answer failed to complete."}
          </div>
        ) : null}

        {statusLabel === null ||
        message.phase === "done" ||
        message.phase === "error" ? null : (
          <ReasoningRoot streaming={message.status === "running"}>
            <ReasoningTrigger active={message.status === "running"} />
            <ReasoningContent aria-busy={message.status === "running"}>
              <ReasoningText>{statusLabel}</ReasoningText>
            </ReasoningContent>
          </ReasoningRoot>
        )}

        {messageBody}

        <MessagePrimitive.Error />
      </div>
    </MessagePrimitive.Root>
  );
};

export { EvidentAssistantMessage };
