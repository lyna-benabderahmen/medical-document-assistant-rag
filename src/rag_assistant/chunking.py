"""Bounded page-local chunks with stable source IDs."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from .ingestion import PageRecord


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    version: str
    location: str
    text: str
    token_count: int
    corpus_version: str


def split_page(
    page: PageRecord, corpus_version: str, *, size: int = 300, overlap: int = 50
) -> list[Chunk]:
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("Require positive size and 0 <= overlap < size")
    if page.status != "ok":
        return []
    # shortcut: whitespace tokens approximate the model tokenizer; replace after encoder validation.
    tokens = list(re.finditer(r"\S+", page.text))
    chunks = []
    for start in range(0, len(tokens), size - overlap):
        words = tokens[start : start + size]
        if not words:
            break
        value = page.text[words[0].start() : words[-1].end()]
        location = page.location
        if location.startswith("lines "):
            first_line = page.text.count("\n", 0, words[0].start()) + 1
            last_line = page.text.count("\n", 0, words[-1].end()) + 1
            location = f"lines {first_line}-{last_line}"
        identity = (
            f"{corpus_version}\0{page.document_id}\0{page.version}\0{location}\0{start}\0{value}"
        )
        chunks.append(
            Chunk(
                hashlib.sha256(identity.encode()).hexdigest()[:24],
                page.document_id,
                page.version,
                location,
                value,
                len(words),
                corpus_version,
            )
        )
        if start + size >= len(tokens):
            break
    return chunks


def chunk_records(
    pages: list[PageRecord], corpus_version: str, *, size: int = 300, overlap: int = 50
) -> list[Chunk]:
    return [
        chunk
        for page in pages
        for chunk in split_page(page, corpus_version, size=size, overlap=overlap)
    ]
