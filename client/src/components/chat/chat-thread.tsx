"use client";

import type { FC } from "react";
import { Thread as AssistantThread } from "@/components/assistant-ui/thread";
import { EvidentAssistantMessage } from "@/components/chat/evident-assistant-message";

const Thread: FC = () => (
  <AssistantThread components={{ AssistantMessage: EvidentAssistantMessage }} />
);

export { Thread };
