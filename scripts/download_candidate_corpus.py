"""Download public CDC candidate PDFs; never approve or index them automatically."""

from __future__ import annotations

import hashlib
import json
import urllib.request
from datetime import date
from pathlib import Path

from pypdf import PdfReader

SOURCES = {
    "disinfection": "Guideline-Disinfection-H.pdf",
    "environmental": "Guideline-Environmental-H.pdf",
    "hand-hygiene": "Guideline-Hand-Hygiene-P.pdf",
    "isolation": "Guideline-Isolation-H.pdf",
    "hcp-infrastructure": "Guideline-Infection-Control-HCP-H.pdf",
    "hcp-selected-infections": "HCP-GL-Update-Selected-Infections-H.pdf",
    "intravascular": "Guideline-BSI-H.pdf",
    "cauti": "Guideline-CAUTI-H.pdf",
    "pneumonia": "Guideline-Healthcare-Associated-Pneumonia-H.pdf",
    "measles": "Guideline-Measles-Interim-IC-Recs-H.pdf",
    "norovirus": "Guideline-Norovirus-H.pdf",
    "mdro": "Guideline-MDRO-H.pdf",
    "cdiff-nicu": "Cdiff-NICU-508.pdf",
    "cdiff-nicu-appendix": "Cdiff-NICU-Appendix-508.pdf",
    "enhanced-barrier": "EnhancedBarrierPrecautions-508.pdf",
    "hcp-parvovirus": "IC-in-HCP-GL-Update-Parvo-Supplement-2025-9-508.pdf",
    "hcp-conjunctivitis": "IC-in-HCP-Update-Conjunctivitis-Supplement-508.pdf",
    "hcp-respiratory": "IC-in-HCP-Update-Viral-Respiratory-Infections-Supplement-508.pdf",
    "hcp-recommendations": "Guideline-Infection-Control-HCP-Recommendations-Only-H.pdf",
    "hcp-immunization": "/mmwr/pdf/rr/rr6007.pdf",
}


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    raw_dir = root / "data/raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for document_id, filename in SOURCES.items():
        url = urllib.request.urljoin("https://www.cdc.gov/infection-control/media/pdfs/", filename)
        target = raw_dir / f"{document_id}.pdf"
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                data = response.read(20_000_001)
            if len(data) > 20_000_000 or not data.startswith(b"%PDF-"):
                raise ValueError("Not a PDF under the 20 MB limit")
            target.write_bytes(data)
            titles = {
                "hand-hygiene": "Guideline for Hand Hygiene in Health-Care Settings (2002)",
                "pneumonia": "Guidelines for Preventing Health-Care–Associated Pneumonia (2003)",
                "enhanced-barrier": "Consideration for Use of Enhanced Barrier Precautions in Skilled Nursing Facilities",
                "hcp-immunization": "Immunization of Health-Care Personnel (2011)",
            }
            title = (
                titles.get(document_id)
                or PdfReader(target).metadata.title
                or document_id.replace("-", " ").title()
            )
            records.append(
                {
                    "document_id": document_id,
                    "filename": target.name,
                    "title": title.strip(),
                    "source_url": url,
                    "version": f"snapshot-{date.today().isoformat()}",
                    "language": "en",
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "approval_status": "candidate",
                }
            )
            print(f"OK {document_id}: {len(data)} bytes")
        except (OSError, ValueError) as exc:
            print(f"FAILED {document_id}: {exc}")
    output = root / "data/candidate-manifest.jsonl"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row) + "\n" for row in records), encoding="utf-8")
    print(f"Saved {len(records)} candidates to {output}")


if __name__ == "__main__":
    main()
