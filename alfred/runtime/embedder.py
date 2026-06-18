"""Embedding backends + pattern exemplar index for Router v3.

The Router's v3 score adds a semantic term: cosine(query, pattern exemplars).
This module owns (a) the backend abstraction, (b) the per-pattern exemplar
index with JSON persistence, and (c) a stdlib cosine — no numpy hard dep.

`sentence-transformers` is OPTIONAL: SentenceTransformerBackend imports it
lazily and raises EmbedderUnavailable when missing; the Router degrades to a
renormalized wilson+regex score. Tests use FakeDeterministicBackend.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .store import PatternStore
    from .types import Pattern


class EmbedderUnavailable(RuntimeError):
    """Raised when the optional embedding dependency is not installed."""


@runtime_checkable
class EmbeddingBackend(Protocol):
    name: str

    def encode(self, texts: list[str]) -> list[list[float]]: ...


class SentenceTransformerBackend:
    """Real backend over the optional `sentence-transformers` package.

    The import happens inside __init__ so that merely importing this module
    never requires the package (no new hard dependency)."""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer  # lazy, optional
        except ImportError as e:
            raise EmbedderUnavailable(
                f"sentence-transformers not installed: {e}"
            ) from e
        self.name = f"st:{model_name}"
        self._model = SentenceTransformer(model_name)

    def encode(self, texts: list[str]) -> list[list[float]]:
        return [[float(x) for x in vec] for vec in self._model.encode(texts)]


class FakeDeterministicBackend:
    """Test-only backend: hashed bag-of-tokens vectors.

    Each token is sha256-hashed onto one of `dim` buckets; a text becomes the
    count vector of its token buckets. This carries NO semantics whatsoever —
    cosine similarity reflects raw token overlap only. It exists so tests are
    deterministic, offline, and dependency-free. Never use outside tests."""

    name = "fake-deterministic"

    def __init__(self, dim: int = 256):
        self.dim = dim

    def encode(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dim
            for token in re.findall(r"[a-z0-9]+", text.lower()):
                h = int.from_bytes(
                    hashlib.sha256(token.encode("utf-8")).digest()[:8], "big"
                )
                vec[h % self.dim] += 1.0
            out.append(vec)
        return out


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity via stdlib math; 0.0 for zero-norm vectors."""
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / ((na ** 0.5) * (nb ** 0.5))


def exemplar_texts(pattern: "Pattern") -> list[str]:
    """Exemplar strings for one pattern: natural_language_intent, then
    metadata.example_queries (realistic phrasings — the strongest signal,
    semantic-router style), then triggers[].components.intent_verbs."""
    texts: list[str] = []
    meta = pattern.raw.get("metadata") or {}
    intent = (meta.get("natural_language_intent") or "").strip()
    if intent:
        texts.append(intent)
    for ex in meta.get("example_queries") or []:
        if isinstance(ex, str) and ex.strip():
            texts.append(ex.strip())
    for trigger in pattern.raw.get("triggers") or []:
        components = (trigger.get("components") or {}) if isinstance(trigger, dict) else {}
        for verb in components.get("intent_verbs") or []:
            if isinstance(verb, str) and verb.strip():
                texts.append(verb.strip())
    return texts


def max_cosine(qvec: list[float], exemplar_vecs: list[list[float]]) -> float:
    """Best match against ANY exemplar — the semantic-router convention.
    Mean-pooling diluted exact-phrase matches below the rescue threshold
    (measured 2026-06-12: query == stored exemplar scored only 0.435)."""
    return max((cosine(qvec, v) for v in exemplar_vecs), default=-1.0)


def build_pattern_index(
    store: "PatternStore",
    backend: EmbeddingBackend,
    cache_path: str | Path | None = None,
) -> dict[str, list[list[float]]]:
    """pattern_id -> list of per-exemplar vectors for every active pattern.

    Vectors are persisted as JSON at `cache_path` keyed by
    "<backend.name>:<sha256(exemplar_text)>" — only stale entries (key not in
    the cache) are re-encoded. Patterns with no exemplar text are skipped
    (the Router renormalizes for them). Entries from the old mean-pooled
    cache format (flat vector) are treated as stale and re-encoded."""
    cache: dict[str, list[list[float]]] = {}
    path = Path(cache_path).expanduser() if cache_path is not None else None
    if path is not None and path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cache = data
        except (OSError, json.JSONDecodeError):
            cache = {}

    index: dict[str, list[list[float]]] = {}
    dirty = False
    for pattern in store.active_patterns():
        texts = exemplar_texts(pattern)
        if not texts:
            continue
        exemplar_text = "\n".join(texts)
        sha = hashlib.sha256(exemplar_text.encode("utf-8")).hexdigest()
        key = f"{backend.name}:{sha}"
        vecs = cache.get(key)
        if not (vecs and isinstance(vecs[0], list)):  # miss or old flat format
            vecs = backend.encode(texts)
            cache[key] = vecs
            dirty = True
        index[pattern.id] = vecs

    if dirty and path is not None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(json.dumps(cache), encoding="utf-8")
            tmp.replace(path)
        except OSError:
            pass  # persistence is best-effort; the in-memory index is intact
    return index
