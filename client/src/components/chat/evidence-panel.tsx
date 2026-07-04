"use client";

import type { FC } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { AnswerDetail } from "@/lib/types";

interface EvidencePanelProps {
  answer: AnswerDetail | null;
  selectedEvidenceId: string | null;
}

const EvidencePanel: FC<EvidencePanelProps> = ({
  answer,
  selectedEvidenceId,
}) => {
  const answerEvidence = Array.isArray(answer?.evidence) ? answer.evidence : [];

  if (answer === null || answerEvidence.length === 0) {
    return (
      <div className="flex h-full items-center justify-center px-6 text-center text-muted-foreground text-sm">
        Evidence for the current Answer will appear here.
      </div>
    );
  }

  if (selectedEvidenceId === null) {
    return (
      <div className="flex h-full items-center justify-center px-6 text-center text-muted-foreground text-sm">
        Select a citation to inspect its supporting Evidence.
      </div>
    );
  }

  const selectedEvidence =
    answerEvidence.find((evidence) => evidence.id === selectedEvidenceId) ??
    null;

  if (selectedEvidence === null) {
    return (
      <div className="flex h-full items-center justify-center px-6 text-center text-muted-foreground text-sm">
        The selected Evidence is not available for this Answer.
      </div>
    );
  }

  const otherEvidence = answerEvidence.filter(
    (evidence) => evidence.id !== selectedEvidenceId
  );

  return (
    <ScrollArea className="h-full">
      <div className="flex flex-col gap-4 p-4">
        <Card>
          <CardHeader className="gap-2">
            <div className="flex items-center justify-between gap-2">
              <CardTitle className="text-base">
                {selectedEvidence.document_title ?? "Selected Evidence"}
              </CardTitle>
              <Badge variant="secondary">Selected</Badge>
            </div>
            <div className="text-muted-foreground text-sm">
              {selectedEvidence.context_header ?? "Supporting Evidence"}
            </div>
          </CardHeader>
          <CardContent className="flex flex-col gap-2 text-sm">
            {selectedEvidence.page === null ? null : (
              <div className="text-muted-foreground">
                Page {selectedEvidence.page}
              </div>
            )}
            <p className="whitespace-pre-wrap leading-relaxed">
              {selectedEvidence.content}
            </p>
          </CardContent>
        </Card>

        {otherEvidence.length === 0 ? null : (
          <div className="flex flex-col gap-3">
            <div className="text-muted-foreground text-sm">Other Evidence</div>
            {otherEvidence.map((evidence, index) => (
              <Card key={evidence.id}>
                <CardHeader className="gap-2">
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle className="text-base">
                      {evidence.document_title ?? `Evidence ${index + 1}`}
                    </CardTitle>
                    <Badge variant="outline">{index + 1}</Badge>
                  </div>
                  <div className="text-muted-foreground text-sm">
                    {evidence.context_header ?? "Supporting Evidence"}
                  </div>
                </CardHeader>
                <CardContent className="flex flex-col gap-2 text-sm">
                  {evidence.page === null ? null : (
                    <div className="text-muted-foreground">
                      Page {evidence.page}
                    </div>
                  )}
                  <p className="whitespace-pre-wrap leading-relaxed">
                    {evidence.content}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </ScrollArea>
  );
};

export { EvidencePanel };
