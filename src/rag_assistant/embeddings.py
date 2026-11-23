"""Local multilingual E5 embeddings with required document/query prefixes."""

from __future__ import annotations


class Encoder:
    def __init__(
        self,
        model_name: str = "intfloat/multilingual-e5-small",
        revision: str = "614241f622f53c4eeff9890bdc4f31cfecc418b3",
    ) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.revision = revision
        self.model = SentenceTransformer(model_name, revision=revision)
        self.max_tokens = self.model.max_seq_length

    def documents(self, texts: list[str]) -> list[list[float]]:
        prefixed = ["passage: " + text for text in texts]
        self._check_lengths(prefixed)
        return self.model.encode(prefixed, normalize_embeddings=True).tolist()

    def query(self, question: str) -> list[float]:
        if not question.strip():
            raise ValueError("Question is empty")
        prefixed = "query: " + question
        self._check_lengths([prefixed])
        return self.model.encode(prefixed, normalize_embeddings=True).tolist()

    def _check_lengths(self, texts: list[str]) -> None:
        lengths = [len(ids) for ids in self.model.tokenizer(texts, truncation=False)["input_ids"]]
        if any(length > self.max_tokens for length in lengths):
            raise ValueError(f"Input exceeds the encoder limit of {self.max_tokens} tokens")
