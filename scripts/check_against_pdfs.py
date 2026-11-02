"""Sanity check (not a substitute for human review): every number in an expected answer
should appear on the cited page of the cited PDF. Requires `pdftotext` (poppler).

Usage: python scripts/check_against_pdfs.py --pdf-dir path/to/pdfs [--dir data/eval]
"""
import argparse, json, os, re, subprocess

def page_text(pdf, page):
    out = subprocess.run(["pdftotext", "-layout", "-f", str(page), "-l", str(page), pdf, "-"], capture_output=True, text=True)
    return re.sub(r"\s+", " ", out.stdout.replace("\u2019", "'")).lower()

def numbers(s):
    return set(re.findall(r"\d+(?:[.,]\d+)?", s.replace("\u2019", "'")))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf-dir", required=True)
    ap.add_argument("--dir", default="data/eval")
    a = ap.parse_args()
    manifest = json.load(open(f"{a.dir}/corpus_manifest.json", encoding="utf-8"))["documents"]
    bad = 0
    for split in ("dev", "test"):
        for line in open(f"{a.dir}/{split}.jsonl", encoding="utf-8"):
            r = json.loads(line)
            if not r["answerable"]: continue
            pdf = os.path.join(a.pdf_dir, manifest[r["document_id"]]["file"])
            pages = [r["page"]] + [s["page"] for s in r["alt_sources"] if s["document_id"] == r["document_id"]]
            text = " ".join(page_text(pdf, p) for p in pages)
            missing = [n for n in numbers(r["expected_answer"]) if n not in text and n.replace(",", ".") not in text]
            if missing:
                bad += 1; print(f"{r['question_id']} ({r['document_id']} p.{r['page']}): numbers not found on page: {missing}")
    print("done:", "all numbers found" if not bad else f"{bad} question(s) to double-check by hand")

if __name__ == "__main__":
    main()
