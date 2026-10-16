"""Deterministic reciprocal rank fusion over source lines."""
from dataclasses import dataclass, asdict
from typing import Callable, Iterable, List

RRF_K = 60


@dataclass
class FusedSnippet:
    uri: str
    start_line: int
    end_line: int
    content: str
    score: float

    def to_dict(self):
        return asdict(self)


def fuse_results(retrieved_sets: Iterable, ranking_identities: Callable) -> List[FusedSnippet]:
    """Return ranked lines; each branch contributes only its best containing rank.

    Each item in retrieved_sets must be an ordered ranking.
    Ties retain first-seen order, with lines within a snippet in source order.
    """
    evidence = {}
    for ranking in retrieved_sets:
        if isinstance(ranking, (set, frozenset)):
            raise TypeError("RRF requires ordered rankings, not sets")
        seen = set()
        for rank, snippet in enumerate(ranking, start=1):
            lines = snippet.content.split("\n")
            identities = ranking_identities(snippet)
            for offset, identity in enumerate(identities):
                if offset >= len(lines) or identity in seen:
                    continue
                seen.add(identity)
                if identity not in evidence:
                    evidence[identity] = FusedSnippet(
                        snippet.uri, snippet.start_line + offset,
                        snippet.start_line + offset, lines[offset], 0.0,
                    )
                evidence[identity].score += 1.0 / (RRF_K + rank)
    return sorted(evidence.values(), key=lambda item: -item.score)


def merge_adjacent_lines(lines: List[FusedSnippet]) -> List[FusedSnippet]:
    """Reconstruct selected lines, then order spans by their strongest line rank."""
    priorities = {(line.uri, line.start_line): i for i, line in enumerate(lines)}
    spans = []
    span_priorities = []
    for line in sorted(lines, key=lambda item: (item.uri, item.start_line)):
        priority = priorities[line.uri, line.start_line]
        if spans and spans[-1].uri == line.uri and spans[-1].end_line + 1 == line.start_line:
            spans[-1].content += "\n" + line.content
            spans[-1].end_line = line.end_line
            spans[-1].score = max(spans[-1].score, line.score)
            span_priorities[-1] = min(span_priorities[-1], priority)
        else:
            spans.append(FusedSnippet(**line.to_dict()))
            span_priorities.append(priority)
    return [span for _, span in sorted(zip(span_priorities, spans), key=lambda pair: pair[0])]
