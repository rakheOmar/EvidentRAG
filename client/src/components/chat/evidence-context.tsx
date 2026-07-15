"use client";

import {
	createContext,
	type FC,
	type ReactNode,
	use,
	useCallback,
	useMemo,
	useState,
} from "react";

interface EvidenceContextValue {
	clearEvidence: () => void;
	selectEvidence: (messageId: string, ids: string[]) => void;
	selectedEvidenceIds: string[];
	selectedMessageId: string | null;
}

const EvidenceContext = createContext<EvidenceContextValue | null>(null);

export const EvidencePanelProvider: FC<{ children: ReactNode }> = ({
	children,
}) => {
	const [selectedEvidenceIds, setSelectedEvidenceIds] = useState<string[]>([]);
	const [selectedMessageId, setSelectedMessageId] = useState<string | null>(
		null,
	);

	const selectEvidence = useCallback((messageId: string, ids: string[]) => {
		setSelectedMessageId(messageId);
		setSelectedEvidenceIds(ids);
	}, []);

	const clearEvidence = useCallback(() => {
		setSelectedMessageId(null);
		setSelectedEvidenceIds([]);
	}, []);

	const value = useMemo(
		() => ({
			clearEvidence,
			selectEvidence,
			selectedEvidenceIds,
			selectedMessageId,
		}),
		[clearEvidence, selectEvidence, selectedEvidenceIds, selectedMessageId],
	);

	return (
		<EvidenceContext.Provider value={value}>
			{children}
		</EvidenceContext.Provider>
	);
};

export function useEvidencePanel(): EvidenceContextValue {
	const ctx = use(EvidenceContext);
	if (!ctx) {
		throw new Error(
			"useEvidencePanel must be used within an EvidencePanelProvider",
		);
	}
	return ctx;
}
