from __future__ import annotations

from typing import List

from fastapi import FastAPI
from pydantic import BaseModel

from rosemary_memory.memory.embeddings import embed_texts_local


app = FastAPI(title="Rosemary Embeddings Service")


class EmbedRequest(BaseModel):
    texts: List[str]


class EmbedResponse(BaseModel):
    vectors: List[List[float]]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/embed", response_model=EmbedResponse)
def embed(request: EmbedRequest) -> EmbedResponse:
    vectors = embed_texts_local(request.texts)
    return EmbedResponse(vectors=vectors)
