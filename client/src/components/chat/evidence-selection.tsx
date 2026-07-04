"use client";

import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useState,
} from "react";

interface EvidenceSelectionContextValue {
  selectEvidence: (evidenceId: string | null) => void;
  selectedEvidenceId: string | null;
}

const EvidenceSelectionContext =
  createContext<EvidenceSelectionContextValue | null>(null);

function EvidenceSelectionProvider({ children }: PropsWithChildren) {
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(
    null
  );

  const selectEvidence = useCallback((evidenceId: string | null) => {
    setSelectedEvidenceId(evidenceId);
  }, []);

  return (
    <EvidenceSelectionContext.Provider
      value={{ selectEvidence, selectedEvidenceId }}
    >
      {children}
    </EvidenceSelectionContext.Provider>
  );
}

function useEvidenceSelection() {
  const context = useContext(EvidenceSelectionContext);

  if (context === null) {
    throw new Error(
      "useEvidenceSelection must be used within an EvidenceSelectionProvider"
    );
  }

  return context;
}

export {
  EvidenceSelectionContext,
  EvidenceSelectionProvider,
  useEvidenceSelection,
};
