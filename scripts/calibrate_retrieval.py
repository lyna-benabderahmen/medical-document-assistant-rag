"""Select top-k and a cosine-distance cutoff using development questions only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rag_assistant.calibration import DevelopmentResult, choose_threshold
from rag_assistant.embeddings import Encoder
from rag_assistant.retrieval import retrieve


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("questions", type=Path)
    parser.add_argument("index_dir", type=Path)
    parser.add_argument("corpus_version")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    questions = [
        json.loads(line)
        for line in args.questions.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not questions or any(q.get("split") != "development" for q in questions):
        raise ValueError("Calibration accepts development questions only")
    encoder = Encoder()
    candidates = []
    for top_k in (3, 5, 8):
        rows = [
            DevelopmentResult(
                q["answerable"],
                q.get("document_id"),
                q.get("location"),
                retrieve(q["question"], args.corpus_version, args.index_dir, encoder, top_k=top_k),
            )
            for q in questions
        ]
        threshold, counts = choose_threshold(rows)
        score = (
            counts["source_correct"] / counts["answerable"]
            + counts["correct_abstention"] / counts["absent"]
        ) / 2
        candidates.append(
            {"top_k": top_k, "max_distance": threshold, "balanced_score": score, **counts}
        )
    chosen = max(
        candidates, key=lambda row: (row["balanced_score"], row["source_correct"], -row["top_k"])
    )
    report = {
        "corpus_version": args.corpus_version,
        "encoder": encoder.model_name,
        "revision": encoder.revision,
        "development_questions": len(questions),
        "chosen": chosen,
        "candidates": candidates,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
