"use client";

import { AuiIf, ThreadPrimitive, useAuiState } from "@assistant-ui/react";
import type { FC } from "react";

export const ThreadFollowupSuggestions: FC = () => {
	const suggestions = useAuiState((s) => s.thread.suggestions);
	return (
		<AuiIf condition={(s) => !(s.thread.isEmpty || s.thread.isRunning)}>
			<div className="aui-thread-followup-suggestions flex min-h-8 items-center justify-center gap-2">
				{suggestions?.map((suggestion, idx) => (
					<ThreadPrimitive.Suggestion
						autoSend
						className="aui-thread-followup-suggestion rounded-full border bg-background px-3 py-1 text-sm transition-colors ease-in hover:bg-muted/80"
						key={idx}
						method="replace"
						prompt={suggestion.prompt}
					>
						{suggestion.prompt}
					</ThreadPrimitive.Suggestion>
				))}
			</div>
		</AuiIf>
	);
};
