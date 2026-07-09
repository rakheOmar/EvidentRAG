"use client";

import {
  createContext,
  type FC,
  type ReactNode,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";

interface EvidenceContextValue {
  clearEvidence: () => void;
  selectEvidence: (ids: string[]) => void;
  selectedEvidenceIds: string[];
}

const EvidenceContext = createContext<EvidenceContextValue | null>(null);

export const EvidencePanelProvider: FC<{ children: ReactNode }> = ({
  children,
}) => {
  const [selectedEvidenceIds, setSelectedEvidenceIds] = useState<string[]>([]);

  const selectEvidence = useCallback((ids: string[]) => {
    setSelectedEvidenceIds(ids);
  }, []);

  const clearEvidence = useCallback(() => {
    setSelectedEvidenceIds([]);
  }, []);

  const value = useMemo(
    () => ({ clearEvidence, selectEvidence, selectedEvidenceIds }),
    [clearEvidence, selectEvidence, selectedEvidenceIds]
  );

  return (
    <EvidenceContext.Provider value={value}>
      {children}
    </EvidenceContext.Provider>
  );
};

export function useEvidencePanel(): EvidenceContextValue {
  const ctx = useContext(EvidenceContext);
  if (!ctx) {
    throw new Error(
      "useEvidencePanel must be used within an EvidencePanelProvider"
    );
  }
  return ctx;
}
