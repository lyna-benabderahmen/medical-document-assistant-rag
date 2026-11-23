# Technical report draft

## Purpose and scope

This academic prototype is intended to answer staff reference questions using only an approved, versioned infection prevention and control corpus. It is **not for medical use**. It does not process real patient data or connect to Doctoline systems. See [scope and decisions](SCOPE_AND_DECISIONS.md) and the original [technical architecture](TECHNICAL_ARCHITECTURE.md).

## Implemented retrieval flow

1. Validate a JSONL manifest, approval status, file type, file size and SHA-256 checksum. Reject duplicate content and unapproved records.
2. Extract PDF text page by page with 1-based page numbers. Flag blank/scanned or failed pages. Extract UTF-8 TXT and preserve line ranges.
3. Split text within its source page into stable-ID overlapping chunks. Record document ID, document version, source location and corpus version.
4. Encode passages with the pinned multilingual E5 model and required `passage:` prefix. Reject inputs beyond the model's 512-token limit.
5. Build a versioned persistent Chroma collection with explicit cosine distance. Verify the count; delete failed new collections without changing older versions.
6. Encode questions with `query:`, retrieve top-k chunks, verify encoder/corpus identity and optionally apply a development-calibrated distance threshold.

The implemented modules are in `src/rag_assistant/`. Commands and reproducible setup are in [SETUP.md](SETUP.md). The 20 downloaded CDC PDFs are registered as **candidates** in `data/candidate-manifest.jsonl`; raw PDFs are ignored by Git. The course/supervisor must review and approve exact documents before an operational index is built.

## Validation performed

- Six deterministic tests passed for TXT line references and checksum failure, scanned/blank PDF flagging, manifest approval and duplicate checks, stable page-local chunk IDs, persistent Chroma reload, cross-version protection and threshold selection.
- Ruff passed.
- A real pinned E5 model produced a 384-dimensional query vector and retrieved the expected synthetic source from a persisted Chroma index.
- The 20 candidate PDFs were downloaded with PDF signatures and SHA-256 checksums. Page counts range from 4 to 241; a preliminary text extraction found no fully blank pages. Human source-to-text comparison remains necessary.

## Evaluation protocol and current results

Use separate development questions to compare chunk size 200/300/400, top-k 3/5/8, and select the distance threshold. Freeze corpus, encoder revision, index and settings before opening the final 60-question set. The final set is planned as 45 answerable and 15 absent questions. Report raw counts and denominators for retrieval source recall, generated citation accuracy, answer grounding, answer coverage, correct abstention and latency. Keep original and rerun outputs distinct.

**No final performance result is claimed.** The final question set, Lyna's generation/citation/UI modules, approved corpus and supervisor rubric are not present in this branch. Citation accuracy and grounding require generated answers plus human review; retrieval recall alone is not a substitute.

## Remaining integration and limitations

- Obtain approval of corpus and rubric; review superseded or conflicting CDC editions and PDF text against originals.
- Integrate generation, citation validation and interface changes after teammate PRs and peer review.
- Calibrate and evaluate on actual questions; fix failures and rerun without overwriting raw results.
- Verify a clean installation, end-to-end demo and report review before release.
- Complete two timed rehearsals with both team members, speaking roles, jury questions, backup demo and final submission checklist. These are team actions and cannot be verified from code alone.
