"""Retrieve traceable evidence and abstain when calibrated evidence is absent."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .index import collection_name


@dataclass(frozen=True)
class Hit:
    chunk_id: str
    text: str
    document_id: str
    version: str
    location: str
    distance: float


def retrieve(
    question: str,
    corpus_version: str,
    index_dir: Path,
    encoder,
    *,
    top_k: int = 5,
    max_distance: float | None = None,
) -> list[Hit]:
    if top_k < 1:
        raise ValueError("top_k must be positive")
    if not question.strip():
        return []
    import chromadb

    name = collection_name(corpus_version)
    build = json.loads((index_dir / f"{name}.json").read_text(encoding="utf-8"))
    if (
        build["encoder"] != encoder.model_name
        or build["revision"] != getattr(encoder, "revision", None)
        or build["corpus_version"] != corpus_version
    ):
        raise ValueError("Index and encoder/corpus configuration differ")
    collection = chromadb.PersistentClient(path=str(index_dir)).get_collection(name)
    if not collection.count():
        return []
    results = collection.query(
        query_embeddings=[encoder.query(question)],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )
    hits = []
    for chunk_id, text, meta, distance in zip(
        results["ids"][0], results["documents"][0], results["metadatas"][0], results["distances"][0]
    ):
        if meta["corpus_version"] != corpus_version:
            raise ValueError("Cross-corpus result")
        if max_distance is None or distance <= max_distance:
            hits.append(
                Hit(
                    chunk_id, text, meta["document_id"], meta["version"], meta["location"], distance
                )
            )
    return hits
