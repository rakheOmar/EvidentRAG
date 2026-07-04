"use client";

import { createContext, type PropsWithChildren, useContext } from "react";

import type { EvidentChatMessage } from "@/lib/types";

interface EvidentMessagesContextValue {
  messages: EvidentChatMessage[];
}

const EvidentMessagesContext =
  createContext<EvidentMessagesContextValue | null>(null);

function EvidentMessagesProvider({
  children,
  messages,
}: PropsWithChildren<EvidentMessagesContextValue>) {
  return (
    <EvidentMessagesContext.Provider value={{ messages }}>
      {children}
    </EvidentMessagesContext.Provider>
  );
}

function useEvidentMessages() {
  const context = useContext(EvidentMessagesContext);

  if (context === null) {
    throw new Error(
      "useEvidentMessages must be used within an EvidentMessagesProvider"
    );
  }

  return context;
}

export { EvidentMessagesProvider, useEvidentMessages };
