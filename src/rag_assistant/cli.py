"""Reproducible corpus ingestion, index build and retrieval commands."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .chunking import chunk_records
from .embeddings import Encoder
from .index import build_index
from .ingestion import PageRecord, ingest
from .retrieval import retrieve


def main() -> None:
    parser = argparse.ArgumentParser(description="Academic prototype — not for medical use")
    commands = parser.add_subparsers(dest="command", required=True)
    extraction = commands.add_parser("ingest")
    extraction.add_argument("manifest", type=Path)
    extraction.add_argument("corpus_dir", type=Path)
    extraction.add_argument("pages", type=Path)
    building = commands.add_parser("build")
    building.add_argument("pages", type=Path)
    building.add_argument("index_dir", type=Path)
    building.add_argument("corpus_version")
    building.add_argument("--size", type=int, default=300)
    building.add_argument("--overlap", type=int, default=50)
    query = commands.add_parser("query")
    query.add_argument("index_dir", type=Path)
    query.add_argument("corpus_version")
    query.add_argument("question")
    query.add_argument("--top-k", type=int, default=5)
    query.add_argument("--max-distance", type=float)
    args = parser.parse_args()
    if args.command == "ingest":
        result = ingest(args.manifest, args.corpus_dir, args.pages)
    else:
        encoder = Encoder()
        if args.command == "build":
            pages = [
                PageRecord(**json.loads(line))
                for line in args.pages.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            chunks = chunk_records(pages, args.corpus_version, size=args.size, overlap=args.overlap)
            result = build_index(chunks, encoder, args.index_dir, args.corpus_version)
            result.update(
                {"size": args.size, "overlap": args.overlap, "model_max_tokens": encoder.max_tokens}
            )
        else:
            result = [
                asdict(hit)
                for hit in retrieve(
                    args.question,
                    args.corpus_version,
                    args.index_dir,
                    encoder,
                    top_k=args.top_k,
                    max_distance=args.max_distance,
                )
            ]
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
