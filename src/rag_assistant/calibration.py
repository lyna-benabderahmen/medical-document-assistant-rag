"""Choose retrieval settings on development questions only."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise


@dataclass(frozen=True)
class DevelopmentResult:
    answerable: bool
    expected_document_id: str | None
    expected_location: str | None
    hits: list


def choose_threshold(rows: list[DevelopmentResult]) -> tuple[float, dict]:
    if (
        not rows
        or not any(row.answerable for row in rows)
        or not any(not row.answerable for row in rows)
    ):
        raise ValueError("Need both answerable and absent development questions")
    distances = sorted({hit.distance for row in rows for hit in row.hits})
    if not distances:
        raise ValueError("No retrieved development hits")
    candidates = (
        [distances[0] - 0.000001]
        + [(a + b) / 2 for a, b in pairwise(distances)]
        + [distances[-1] + 0.000001]
    )
    best = None
    for threshold in candidates:
        source_correct = 0
        abstained = 0
        coverage = 0
        for row in rows:
            accepted = [hit for hit in row.hits if hit.distance <= threshold]
            if row.answerable:
                coverage += bool(accepted)
                source_correct += any(
                    (hit.document_id, hit.location)
                    == (row.expected_document_id, row.expected_location)
                    for hit in accepted
                )
            else:
                abstained += not accepted
        positives = sum(row.answerable for row in rows)
        negatives = len(rows) - positives
        balanced = (source_correct / positives + abstained / negatives) / 2
        score = (balanced, source_correct, abstained, -threshold)
        if best is None or score > best[0]:
            best = (
                score,
                threshold,
                {
                    "source_correct": source_correct,
                    "answerable": positives,
                    "correct_abstention": abstained,
                    "absent": negatives,
                    "answer_coverage": coverage,
                },
            )
    return best[1], best[2]
