"""Quality checks shared by enrichment entry points."""

from __future__ import annotations

import re
from typing import Any


_MARKDOWN_PREFIX = re.compile(r"^\s{0,3}(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+)")
_SENTENCE_END = re.compile(r"[.!?]+(?=\s|$)")


def intent_sentence_count(intent: Any) -> int:
    """Counts terminal sentences without treating Markdown markers as content."""
    text = "\n".join(_MARKDOWN_PREFIX.sub("", line) for line in str(intent or "").splitlines())
    return len(_SENTENCE_END.findall(text.strip()))


def has_recommended_intent_length(intent: Any) -> bool:
    """Whether an intent contains the recommended two to three sentences."""
    return 2 <= intent_sentence_count(intent) <= 3
