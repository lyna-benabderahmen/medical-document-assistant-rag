# Scope and implementation decisions

## MVP

Search an approved, versioned PDF/TXT corpus for staff reference questions and show exact document/page or TXT line evidence. Use English questions first. Treat French support as an evaluation target after the corpus and encoder are validated. Return no answer when calibrated evidence is absent. No patient records, clinical recommendations, live Doctoline data or external model calls.

## Architecture

`manifest.jsonl` → checksum and approval validation → page/line extraction → page-local chunks → local multilingual E5 embeddings → versioned Chroma cosine index → top-k retrieval → evidence threshold → answer generation and citation checking by the teammate's modules → Streamlit display.

The current branch implements the Oussema-owned extraction, chunking, index and retrieval modules. The LLM adapter, answer schema, citations and UI are separate team work and must be integrated and peer reviewed before release.

## Decisions still requiring evidence

- Corpus: 20 CDC candidates are registered in [CORPUS_CANDIDATES.md](CORPUS_CANDIDATES.md). Approval, exact editions and files are pending.
- Extraction limit: 20 MB/file and 300 pages/file. The candidate audit found two guidelines over the original 200-page proposal (211 and 241 pages), so the page cap was raised without omitting them.
- Encoder: `intfloat/multilingual-e5-small` at revision `614241f622f53c4eeff9890bdc4f31cfecc418b3` is the pinned MIT-licensed baseline. Its model card requires `query:` and `passage:` prefixes and describes a 512-token maximum. Hardware and French/English retrieval quality still need checking on approved development questions.
- Chunking: 300 whitespace tokens with 50 overlap is an implementation baseline. Check the selected encoder's actual tokenizer and compare 200/300/400 on development questions before finalizing.
- Retrieval: start with top-k 5; compare 3/5/8 and calibrate a cosine-distance threshold on development questions only. The final 60 questions must stay untouched until the configuration is frozen.
- Model/runtime: Ollama model and resource budget are pending a hardware check and supervisor decision. No model performance is claimed.
- Rubric: target 41/45 correct document **and** page among answerable questions; report raw counts, coverage and failures. The supervisor must approve the final rubric.

Do not mark ClickUp tasks complete before acceptance checks, peer review and integration verification.
