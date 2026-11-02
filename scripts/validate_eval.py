"""Validate the evaluation dataset. Exit code 1 on any error (usable in CI).

Usage: python scripts/validate_eval.py [--dir data/eval]
"""
import argparse, json, re, sys
from collections import Counter

REQUIRED = ["question_id", "split", "question", "expected_answer", "answerable", "document_id",
            "document_version", "page", "alt_sources", "question_type", "no_answer_type",
            "notes", "status", "reviewed_by", "dataset_version"]
NO_ANSWER_TYPES = {"near_miss", "related_gap", "out_of_scope"}


def load(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def norm(s):
    return re.sub(r"\W+", " ", s.lower()).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/eval")
    args = ap.parse_args()
    manifest = json.load(open(f"{args.dir}/corpus_manifest.json", encoding="utf-8"))
    docs = manifest["documents"]
    dev, test = load(f"{args.dir}/dev.jsonl"), load(f"{args.dir}/test.jsonl")
    errs, seen = [], set()

    for name, rows, prefix in (("dev", dev, "D-"), ("test", test, "T-")):
        for r in rows:
            q = r.get("question_id", "?")
            missing = [k for k in REQUIRED if k not in r]
            if missing:
                errs.append(f"{q}: missing fields {missing}"); continue
            if q in seen: errs.append(f"{q}: duplicate id")
            seen.add(q)
            if r["split"] != name: errs.append(f"{q}: split={r['split']} but file is {name}")
            if not q.startswith(prefix): errs.append(f"{q}: id must start with {prefix}")
            if not r["question"].strip() or not r["expected_answer"].strip(): errs.append(f"{q}: empty question/answer")
            if r["dataset_version"] != manifest["dataset_version"]: errs.append(f"{q}: dataset_version mismatch")
            sources = []
            if r["answerable"]:
                if r["document_id"] not in docs: errs.append(f"{q}: unknown document_id {r['document_id']}")
                elif r["document_version"] != docs[r["document_id"]]["version"]: errs.append(f"{q}: version differs from manifest")
                if not isinstance(r["page"], int): errs.append(f"{q}: answerable needs an integer page")
                if r["no_answer_type"] is not None: errs.append(f"{q}: answerable must have no_answer_type null")
                sources.append((r["document_id"], r["page"]))
                for s in r["alt_sources"]: sources.append((s.get("document_id"), s.get("page")))
            else:
                if r["document_id"] or r["page"] or r["document_version"] or r["alt_sources"]:
                    errs.append(f"{q}: no-answer must have null source fields")
                if r["no_answer_type"] not in NO_ANSWER_TYPES: errs.append(f"{q}: bad no_answer_type")
            for d, p in sources:
                if d in docs and not (isinstance(p, int) and 1 <= p <= docs[d]["pages"]):
                    errs.append(f"{q}: page {p} outside {d} (1-{docs[d]['pages']})")

    # split sizes and balance
    c = Counter(r["answerable"] for r in test)
    if (c[True], c[False]) != (45, 15): errs.append(f"test must be 45 answerable + 15 no-answer, got {dict(c)}")
    cd = Counter(r["answerable"] for r in dev)
    if cd[True] < 10 or cd[False] < 4: errs.append(f"dev too small: {dict(cd)}")

    # leakage between dev and test
    tq = {norm(r["question"]) for r in test}
    for r in dev:
        if norm(r["question"]) in tq: errs.append(f"{r['question_id']}: question also in test")
    tsrc = {(r["document_id"], r["page"], norm(r["expected_answer"])) for r in test if r["answerable"]}
    for r in dev:
        if r["answerable"] and (r["document_id"], r["page"], norm(r["expected_answer"])) in tsrc:
            errs.append(f"{r['question_id']}: same passage and answer as a test question")

    # coverage report (informational)
    cov = Counter(r["document_id"] for r in test if r["answerable"])
    print("test coverage per document:", dict(sorted(cov.items())))
    print("no-answer types (test):", dict(Counter(r["no_answer_type"] for r in test if not r["answerable"])))
    print("OK" if not errs else "\n".join(errs))
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
