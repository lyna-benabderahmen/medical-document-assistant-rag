"""Build versioned Chroma indexes without replacing the previous version on failure."""

from __future__ import annotations

import json
from pathlib import Path

from .chunking import Chunk


def collection_name(corpus_version: str) -> str:
    import hashlib

    return "corpus_" + hashlib.sha256(corpus_version.encode()).hexdigest()[:16]


def build_index(chunks: list[Chunk], encoder, index_dir: Path, corpus_version: str) -> dict:
    if not chunks or any(c.corpus_version != corpus_version for c in chunks):
        raise ValueError("Need nonempty chunks from one corpus version")
    import chromadb

    index_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(index_dir))
    name = collection_name(corpus_version)
    if name in [c.name for c in client.list_collections()]:
        raise ValueError(f"Index already exists for {corpus_version}; choose a new version")
    collection = client.create_collection(name=name, metadata={"hnsw:space": "cosine"})
    try:
        for start in range(0, len(chunks), 32):
            batch = chunks[start : start + 32]
            vectors = encoder.documents([c.text for c in batch])
            collection.add(
                ids=[c.chunk_id for c in batch],
                documents=[c.text for c in batch],
                embeddings=vectors,
                metadatas=[
                    {
                        "document_id": c.document_id,
                        "version": c.version,
                        "location": c.location,
                        "corpus_version": c.corpus_version,
                    }
                    for c in batch
                ],
            )
        if collection.count() != len(chunks):
            raise RuntimeError("Index count mismatch")
        build = {
            "corpus_version": corpus_version,
            "collection": name,
            "chunks": len(chunks),
            "encoder": encoder.model_name,
            "revision": getattr(encoder, "revision", None),
        }
        (index_dir / f"{name}.json").write_text(json.dumps(build, indent=2), encoding="utf-8")
        return build
    except Exception:
        client.delete_collection(name)
        raise
