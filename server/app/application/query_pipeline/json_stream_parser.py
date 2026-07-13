from __future__ import annotations

import json
import re


_LIST_ITEM_PATTERN = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")
_STRUCTURAL_MARKDOWN_PATTERN = re.compile(
    r"^\s*(?:#{1,6}\s|```|\$\$|\||[-*+]\s+|\d+[.)]\s+)"
)


def join_segment_texts(parts: list[str]) -> str:
    """Join citation segments without invalidating Markdown block syntax."""
    joined = ""
    previous_part = ""
    for part in (part for part in parts if part):
        if not joined:
            joined = part
            previous_part = part
            continue
        previous_content = previous_part.rstrip()
        current_content = part.lstrip()
        if _LIST_ITEM_PATTERN.match(previous_content) and _LIST_ITEM_PATTERN.match(
            current_content
        ):
            joined = f"{joined.rstrip()}\n{current_content}"
        elif _STRUCTURAL_MARKDOWN_PATTERN.match(
            previous_content
        ) or _STRUCTURAL_MARKDOWN_PATTERN.match(current_content):
            joined = f"{joined.rstrip()}\n\n{current_content}"
        elif previous_part != previous_content or part != current_content:
            joined = f"{joined}{part}"
        else:
            joined = f"{joined} {part}"
        previous_part = part
    return joined


class JsonStreamParser:
    _TEXT_PATTERN = re.compile(r'"text":\s*"((?:[^"\\]|\\.)*)"')
    _LEADING_CODE_FENCE_PATTERN = re.compile(r"^```[a-zA-Z0-9_-]*\s*")
    _TRAILING_CODE_FENCE_PATTERN = re.compile(r"\s*```\s*$")

    def __init__(self) -> None:
        self._buffer = ""
        self._emitted_texts: list[str] = []
        self._emitted_count = 0

    @staticmethod
    def _decode_text(raw: str) -> str:
        try:
            return json.loads(f'"{raw}"')
        except json.JSONDecodeError:
            # Models sometimes emit Markdown/LaTeX commands such as \\mathbf
            # inside a JSON string without escaping the backslash. Preserve
            # those literal commands instead of failing the whole answer.
            safe_raw = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", raw)
            try:
                return json.loads(f'"{safe_raw}"')
            except json.JSONDecodeError:
                return raw

    def feed(self, chunk: str) -> list[str]:
        self._buffer += chunk
        matches = list(self._TEXT_PATTERN.finditer(self._buffer))

        emitted: list[str] = []
        for match in matches[self._emitted_count :]:
            decoded = self._decode_text(match.group(1))
            emitted.append(decoded)
            self._emitted_texts.append(decoded)

        self._emitted_count = len(matches)
        return emitted

    def _extract_evidence_ids(self, text_match: re.Match[str]) -> list[object]:
        after_text = self._buffer[text_match.end() :]
        ids_idx = after_text.find('"evidence_ids":')
        if ids_idx == -1:
            return []
        after_ids_key = after_text[ids_idx + len('"evidence_ids":') :]
        stripped = after_ids_key.lstrip()
        if not stripped.startswith("["):
            return []
        try:
            decoded = json.JSONDecoder()
            arr, _ = decoded.raw_decode(stripped)
            return list(arr)
        except (json.JSONDecodeError, ValueError, TypeError):
            return []

    def get_accumulated_text(self) -> str:
        parts = list(self._emitted_texts)

        remaining = self._buffer
        if self._emitted_count > 0:
            matches = list(self._TEXT_PATTERN.finditer(self._buffer))
            remaining = self._buffer[matches[-1].end() :]

        idx = remaining.rfind('"text":')
        if idx != -1:
            after_colon = remaining[idx + len('"text":') :]
            content_start = after_colon.lstrip()
            if content_start.startswith('"'):
                start_in_remaining = (
                    len(remaining)
                    - len(after_colon)
                    + (len(after_colon) - len(content_start))
                    + 1
                )
                raw_chars: list[str] = []
                i = start_in_remaining
                while i < len(remaining):
                    if remaining[i] == "\\":
                        if i + 1 < len(remaining):
                            raw_chars.append(remaining[i])
                            raw_chars.append(remaining[i + 1])
                        i += 2
                    elif remaining[i] == '"':
                        break
                    else:
                        raw_chars.append(remaining[i])
                        i += 1
                raw = "".join(raw_chars)
                if raw:
                    parts.append(self._decode_text(raw))

        return join_segment_texts(parts)

    def get_segments(self) -> list[dict[str, object]]:
        matches = list(self._TEXT_PATTERN.finditer(self._buffer))
        segments: list[dict[str, object]] = []
        for match in matches:
            text = self._decode_text(match.group(1))
            evidence_ids = self._extract_evidence_ids(match)
            segments.append({"text": text, "evidence_ids": evidence_ids})
        return segments

    def _extract_first_json_value(self, raw: str) -> object | None:
        text = raw.strip()
        if not text:
            return []

        text = self._LEADING_CODE_FENCE_PATTERN.sub("", text, count=1)
        text = self._TRAILING_CODE_FENCE_PATTERN.sub("", text)

        decoder = json.JSONDecoder()
        for start_char in ("[", "{"):
            start_index = text.find(start_char)
            if start_index == -1:
                continue
            try:
                value, _ = decoder.raw_decode(text, start_index)
                return value
            except json.JSONDecodeError:
                continue

        return None

    def parse_final(self) -> list[dict[str, object]]:
        if not self._buffer.strip():
            return []
        result = self._extract_first_json_value(self._buffer)
        if result is None:
            segments = self.get_segments()
            if segments:
                return segments

            raw = self._buffer.strip()
            if not raw.startswith(("[", "{")):
                raw = self._LEADING_CODE_FENCE_PATTERN.sub("", raw, count=1)
                raw = self._TRAILING_CODE_FENCE_PATTERN.sub("", raw).strip()
                if raw:
                    return [{"text": raw, "evidence_ids": []}]
            return []
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            segments = result.get("segments")
            if isinstance(segments, list):
                return segments
            answer = result.get("answer") or result.get("content")
            if isinstance(answer, str) and answer.strip():
                return [{"text": answer, "evidence_ids": []}]
            if isinstance(result.get("text"), str):
                return [
                    {
                        "text": result["text"],
                        "evidence_ids": result.get("evidence_ids", []),
                    }
                ]
            return [result]
        return []
