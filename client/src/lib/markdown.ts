const RICH_MARKDOWN_PATTERN =
	/(^|\n)\s{0,3}(?:#{1,6}\s|[-*+]\s|\d+\.\s|```|>|\|)|!\[[^\]]*\]\([^)]*\)|(?:\$\$|\\\(|\\\[|`)/m;
const LIST_ITEM_PATTERN = /^\s*(?:[-*+]\s+|\d+[.)]\s+)/;
const STRUCTURAL_MARKDOWN_PATTERN =
	/^\s*(?:#{1,6}\s|```|\$\$|\||[-*+]\s+|\d+[.)]\s+)/;
const FULL_WIDTH_HIGHLIGHT_PATTERN = /^\s*(?:```|\$\$|\||[-*+]\s+|\d+[.)]\s+)/;

export function hasRichMarkdown(text: string): boolean {
	return RICH_MARKDOWN_PATTERN.test(text);
}

export function requiresFullWidthHighlight(text: string): boolean {
	return FULL_WIDTH_HIGHLIGHT_PATTERN.test(text);
}

export function isSegmentHighlighted(
	evidenceIds: readonly string[],
	hoveredEvidenceId: string | null,
	selectedEvidenceIds: readonly string[],
): boolean {
	const activeEvidenceIds =
		hoveredEvidenceId === null ? selectedEvidenceIds : [hoveredEvidenceId];
	return evidenceIds.some((id) => activeEvidenceIds.includes(id));
}

export function joinMarkdownSegments(parts: readonly string[]): string {
	let joined = "";
	let previousPart = "";

	for (const part of parts) {
		if (!part) {
			continue;
		}
		if (!joined) {
			joined = part;
			previousPart = part;
			continue;
		}

		const previousContent = previousPart.trimEnd();
		const currentContent = part.trimStart();
		if (
			LIST_ITEM_PATTERN.test(previousContent) &&
			LIST_ITEM_PATTERN.test(currentContent)
		) {
			joined = `${joined.trimEnd()}\n${currentContent}`;
		} else if (
			STRUCTURAL_MARKDOWN_PATTERN.test(previousContent) ||
			STRUCTURAL_MARKDOWN_PATTERN.test(currentContent)
		) {
			joined = `${joined.trimEnd()}\n\n${currentContent}`;
		} else if (previousContent !== previousPart || currentContent !== part) {
			joined += part;
		} else {
			joined += ` ${part}`;
		}
		previousPart = part;
	}

	return joined;
}
