from __future__ import annotations

import json
import re


class JsonStreamParser:
    _SENTENCE_PATTERN = re.compile(r'"sentence":"((?:[^"\\]|\\.)*)"')

    def __init__(self) -> None:
        self._buffer = ""
        self._emitted_count = 0

    def feed(self, chunk: str) -> list[str]:
        self._buffer += chunk
        matches = list(self._SENTENCE_PATTERN.finditer(self._buffer))

        emitted: list[str] = []
        for match in matches[self._emitted_count :]:
            emitted.append(json.loads(f'"{match.group(1)}"'))

        self._emitted_count = len(matches)
        return emitted

    def parse_final(self) -> list[dict[str, object]]:
        if not self._buffer.strip():
            return []
        decoder = json.JSONDecoder()
        result, _ = decoder.raw_decode(self._buffer)
        return result
