"""Extract only registered PDF/TXT documents with traceable locations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class PageRecord:
    document_id: str
    version: str
    location: str
    text: str
    status: str = "ok"


def load_manifest(path: Path) -> list[dict]:
    records = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if not records:
        raise ValueError("Corpus manifest is empty")
    seen = set()
    for record in records:
        required = {
            "document_id",
            "filename",
            "title",
            "source_url",
            "version",
            "language",
            "sha256",
            "approval_status",
        }
        if missing := required - record.keys():
            raise ValueError(f"Missing manifest fields: {sorted(missing)}")
        if record["approval_status"] != "approved":
            raise ValueError(f"Document {record['document_id']} is not approved")
        if not record["document_id"] or not record["version"]:
            raise ValueError("Document ID and version are required")
        if (record["document_id"], record["version"]) in seen:
            raise ValueError("Duplicate document ID and version")
        seen.add((record["document_id"], record["version"]))
        filename = Path(record["filename"])
        if filename.name != record["filename"] or filename.suffix.lower() not in {".pdf", ".txt"}:
            raise ValueError("Manifest filename must be a PDF/TXT basename")
    return records


def extract_document(
    record: dict, corpus_dir: Path, *, max_bytes: int = 20_000_000, max_pages: int = 300
) -> list[PageRecord]:
    path = corpus_dir / record["filename"]
    if path.stat().st_size > max_bytes:
        raise ValueError(f"{path.name}: file exceeds {max_bytes} bytes")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != record["sha256"]:
        raise ValueError(f"{path.name}: SHA-256 does not match manifest")
    if path.suffix.lower() == ".txt":
        text = data.decode("utf-8-sig")
        lines = text.splitlines()
        if not text.strip():
            return [PageRecord(record["document_id"], record["version"], "lines 1-0", "", "empty")]
        return [PageRecord(record["document_id"], record["version"], f"lines 1-{len(lines)}", text)]
    if not data.startswith(b"%PDF-"):
        raise ValueError(f"{path.name}: invalid PDF signature")
    from pypdf import PdfReader

    reader = PdfReader(path, strict=True)
    if len(reader.pages) > max_pages:
        raise ValueError(f"{path.name}: PDF exceeds {max_pages} pages")
    pages = []
    for number, page in enumerate(reader.pages, 1):
        try:
            text = page.extract_text() or ""
            status = "ok" if text.strip() else "empty_or_scanned"
        except Exception as exc:  # noqa: BLE001 - report per-page parser failures without losing page numbers
            text, status = "", f"extraction_error: {type(exc).__name__}"
        pages.append(
            PageRecord(record["document_id"], record["version"], f"page {number}", text, status)
        )
    return pages


def ingest(manifest_path: Path, corpus_dir: Path, output_path: Path) -> dict:
    records = load_manifest(manifest_path)
    checksums = [r["sha256"] for r in records]
    if len(checksums) != len(set(checksums)):
        raise ValueError("Duplicate content checksum in corpus manifest")
    pages, errors = [], []
    for record in records:
        try:
            pages.extend(extract_document(record, corpus_dir))
        except Exception as exc:  # noqa: BLE001 - continue extracting other registered documents
            errors.append({"document_id": record["document_id"], "error": str(exc)})
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "".join(json.dumps(asdict(p), ensure_ascii=False) + "\n" for p in pages), encoding="utf-8"
    )
    return {
        "documents": len(records),
        "pages": len(pages),
        "flagged_pages": sum(p.status != "ok" for p in pages),
        "errors": errors,
    }
