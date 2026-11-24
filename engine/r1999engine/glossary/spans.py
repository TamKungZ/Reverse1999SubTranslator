import re
from dataclasses import dataclass

from ..common_words import BASIC, MEDIUM

NOT_NAMES = frozenset(
    "monday tuesday wednesday thursday friday saturday sunday january february march april may june july august "
    "september october november december i god".split()
)
COMMON = frozenset(BASIC) | frozenset(MEDIUM)
UNKNOWN_NAME = re.compile(r"(?<=[a-z,;:] )([A-Z][a-z]{2,}(?: [A-Z][a-z]{2,})*)")


@dataclass
class Span:
    start: int
    end: int
    canon: str
    kind: str


def unknown_name_spans(text, taken):
    """Capitalised word runs in mid sentence that look like names but are not in the glossary."""
    found = []
    for m in UNKNOWN_NAME.finditer(text):
        first = m.group(1).split(" ")[0].lower()
        if first in COMMON or first in NOT_NAMES:
            continue
        if any(m.start(1) < s.end and m.end(1) > s.start for s in taken):
            continue
        found.append(Span(m.start(1), m.end(1), m.group(1), "name"))
    return found
