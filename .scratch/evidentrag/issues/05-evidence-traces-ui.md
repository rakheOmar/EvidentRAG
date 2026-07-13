Status: done

## What to build

The interactive evidence trace panel. Each sentence in the Answer is highlighted and clickable. Clicking a sentence reveals its supporting Evidence in a side panel: the full passage text, Context Header (showing document section context), Document name, and page number. For Image Anchors, the image + its LLM-generated caption is displayed. The user can visually trace every claim back to its source with one click.

## Acceptance criteria

- [x] Answer sentences are rendered as clickable highlighted elements (different highlight color when active)
- [x] Clicking a sentence opens the Evidence side panel showing all Evidence chunks linked to that sentence
- [x] Evidence panel shows: full passage text, Context Header, Document name, page number
- [x] Image Anchors display the extracted image inline in the Answer and retain the LLM-generated caption as retrievable Evidence
- [x] Clicking a different sentence updates the panel to show that sentence's Evidence
- [x] Evidence UI shows the source Document and page location for retrieved Evidence
- [x] The panel is responsive — side panel on desktop, bottom sheet on mobile widths

## Blocked by

- #04-simple-route-query-pipeline

## Comments

- 2026-07-13: Completed trace-aware Markdown rendering, citation hover highlighting, evidence selection, responsive evidence details, and inline display of retrieved Image Anchors with document/page provenance.
