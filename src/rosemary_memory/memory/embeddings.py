from __future__ import annotations

from typing import Iterable, List

import os

import numpy as np
import httpx
from sentence_transformers import SentenceTransformer


_MODEL = None


def _get_model() -> SentenceTransformer:
    global _MODEL
    if _MODEL is None:
        _MODEL = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _MODEL


def embed_texts_local(texts: Iterable[str]) -> List[list[float]]:
    text_list = list(texts)
    if not text_list:
        return []
    model = _get_model()
    vectors = model.encode(text_list, normalize_embeddings=True)
    return vectors.astype(float).tolist()


def embed_texts(texts: Iterable[str]) -> List[list[float]]:
    text_list = list(texts)
    if not text_list:
        return []

    service_url = os.getenv("EMBEDDING_SERVICE_URL", "").strip()
    if service_url:
        try:
            response = httpx.post(
                f"{service_url.rstrip('/')}/embed",
                json={"texts": text_list},
                timeout=10.0,
            )
            response.raise_for_status()
            payload = response.json()
            vectors = payload.get("vectors")
            if isinstance(vectors, list):
                return vectors
        except Exception:
            # Fall back to local model if service is unavailable.
            pass

    return embed_texts_local(text_list)


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    va = np.asarray(a, dtype=float)
    vb = np.asarray(b, dtype=float)
    if va.size == 0 or vb.size == 0:
        return 0.0
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)
