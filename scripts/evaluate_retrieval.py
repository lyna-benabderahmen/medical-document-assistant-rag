"""Evaluate frozen retrieval questions without changing the index or threshold."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from pathlib import Path

from rag_assistant.embeddings import Encoder
from rag_assistant.retrieval import retrieve


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "questions", type=Path, help="JSONL with id, question, answerable, document_id, location"
    )
    parser.add_argument("index_dir", type=Path)
    parser.add_argument("corpus_version")
    parser.add_argument("output", type=Path)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--max-distance", type=float)
    args = parser.parse_args()
    questions = [
        json.loads(line)
        for line in args.questions.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if any(q.get("split") != "final" for q in questions):
        raise ValueError("Final evaluation accepts frozen final questions only")
    if len(questions) != 60 or sum(bool(q["answerable"]) for q in questions) != 45:
        raise ValueError("Final evaluation requires 45 answerable and 15 absent questions")
    ids = [q["id"] for q in questions]
    if len(ids) != len(set(ids)) or not questions:
        raise ValueError("Questions must be nonempty with unique IDs")
    encoder = Encoder()
    rows = []
    for q in questions:
        started = time.perf_counter()
        hits = retrieve(
            q["question"],
            args.corpus_version,
            args.index_dir,
            encoder,
            top_k=args.top_k,
            max_distance=args.max_distance,
        )
        elapsed = (time.perf_counter() - started) * 1000
        expected = q.get("document_id"), q.get("location")
        correct = (
            any((h.document_id, h.location) == expected for h in hits) if q["answerable"] else False
        )
        rows.append(
            {
                "id": q["id"],
                "answerable": q["answerable"],
                "expected_document_id": expected[0] or "",
                "expected_location": expected[1] or "",
                "retrieved": json.dumps(
                    [
                        {
                            "chunk_id": h.chunk_id,
                            "document_id": h.document_id,
                            "location": h.location,
                            "distance": h.distance,
                        }
                        for h in hits
                    ]
                ),
                "expected_source_retrieved": correct,
                "has_evidence": bool(hits),
                "latency_ms": round(elapsed, 1),
            }
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    answerable = [r for r in rows if r["answerable"]]
    absent = [r for r in rows if not r["answerable"]]
    timings = sorted(r["latency_ms"] for r in rows)
    summary = {
        "questions": len(rows),
        "answerable": len(answerable),
        "absent": len(absent),
        "expected_source_retrieved": sum(r["expected_source_retrieved"] for r in answerable),
        "retrieval_source_recall_at_k": sum(r["expected_source_retrieved"] for r in answerable)
        / len(answerable),
        "answer_coverage": sum(r["has_evidence"] for r in answerable),
        "correct_abstention": sum(not r["has_evidence"] for r in absent),
        "median_latency_ms": statistics.median(timings),
        "p95_latency_ms": timings[max(0, int(0.95 * len(timings)) - 1)],
        "corpus_version": args.corpus_version,
        "top_k": args.top_k,
        "max_distance": args.max_distance,
        "encoder": encoder.model_name,
        "citation_accuracy": None,
        "grounding_accuracy": None,
    }
    args.output.with_suffix(".summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
