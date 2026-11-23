import hashlib
import json

import pytest
from pypdf import PdfWriter

from rag_assistant.calibration import DevelopmentResult, choose_threshold
from rag_assistant.chunking import chunk_records, split_page
from rag_assistant.index import build_index
from rag_assistant.ingestion import PageRecord, extract_document, ingest, load_manifest
from rag_assistant.retrieval import Hit, retrieve


class FakeEncoder:
    model_name = "test-encoder-v1"

    def documents(self, texts):
        return [[1.0, 0.0] if "alpha" in text else [0.0, 1.0] for text in texts]

    def query(self, question):
        return [1.0, 0.0] if "alpha" in question else [0.0, 1.0]


def registered(path, document_id="doc-1"):
    return {
        "document_id": document_id,
        "filename": path.name,
        "title": "Example",
        "source_url": "https://example.org/example",
        "version": "1",
        "language": "en",
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "approval_status": "approved",
    }


def test_txt_extraction_keeps_lines_and_checks_checksum(tmp_path):
    path = tmp_path / "example.txt"
    path.write_text("alpha\nbeta\n", encoding="utf-8")
    record = registered(path)
    pages = extract_document(record, tmp_path)
    assert pages == [PageRecord("doc-1", "1", "lines 1-2", path.read_bytes().decode("utf-8"))]
    record["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="SHA-256"):
        extract_document(record, tmp_path)


def test_blank_pdf_is_flagged_without_losing_page(tmp_path):
    path = tmp_path / "example.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with path.open("wb") as stream:
        writer.write(stream)
    assert extract_document(registered(path), tmp_path) == [
        PageRecord("doc-1", "1", "page 1", "", "empty_or_scanned")
    ]


def test_manifest_rejects_unapproved_and_duplicate_content(tmp_path):
    path = tmp_path / "example.txt"
    path.write_text("alpha", encoding="utf-8")
    record = registered(path)
    record["approval_status"] = "candidate"
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps(record) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not approved"):
        load_manifest(manifest)
    record["approval_status"] = "approved"
    manifest.write_text(
        json.dumps(record) + "\n" + json.dumps({**record, "document_id": "doc-2"}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Duplicate content"):
        ingest(manifest, tmp_path, tmp_path / "pages.jsonl")


def test_chunk_ids_are_stable_and_page_local():
    pages = [
        PageRecord("one", "1", "page 1", "alpha beta gamma delta"),
        PageRecord("one", "1", "page 2", "zeta eta"),
    ]
    chunks = chunk_records(pages, "v1", size=3, overlap=1)
    assert [c.location for c in chunks] == ["page 1", "page 1", "page 2"]
    assert [c.text for c in chunks] == ["alpha beta gamma", "gamma delta", "zeta eta"]
    assert chunks == chunk_records(pages, "v1", size=3, overlap=1)
    with pytest.raises(ValueError):
        split_page(pages[0], "v1", size=3, overlap=3)
    txt_chunks = split_page(
        PageRecord("txt", "1", "lines 1-2", "alpha beta\ngamma delta"), "v1", size=3, overlap=1
    )
    assert [c.location for c in txt_chunks] == ["lines 1-2", "lines 2-2"]


def test_persistent_index_reload_and_corpus_guard(tmp_path):
    chunks = chunk_records(
        [
            PageRecord("one", "1", "page 1", "alpha beta"),
            PageRecord("two", "1", "page 2", "gamma delta"),
        ],
        "v1",
    )
    build_index(chunks, FakeEncoder(), tmp_path, "v1")
    hits = retrieve("alpha", "v1", tmp_path, FakeEncoder(), top_k=2, max_distance=0.2)
    assert [(h.document_id, h.location) for h in hits] == [("one", "page 1")]
    assert retrieve("", "v1", tmp_path, FakeEncoder()) == []
    with pytest.raises(ValueError, match="already exists"):
        build_index(chunks, FakeEncoder(), tmp_path, "v1")
    with pytest.raises(FileNotFoundError):
        retrieve("alpha", "v2", tmp_path, FakeEncoder())


def test_development_threshold_separates_evidence_from_absence():
    rows = [
        DevelopmentResult(True, "one", "page 1", [Hit("a", "alpha", "one", "1", "page 1", 0.1)]),
        DevelopmentResult(False, None, None, [Hit("b", "unrelated", "two", "1", "page 2", 0.8)]),
    ]
    threshold, counts = choose_threshold(rows)
    assert 0.1 < threshold < 0.8
    assert counts["source_correct"] == counts["correct_abstention"] == 1
