import json
import math
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
import google.generativeai as genai


EMBEDDING_MODEL = "models/text-embedding-004"

# Index file that should contain a list of objects:
# {
#   "title": str,
#   "url": str,
#   "text": str,
#   "embedding": [float, ...],
#   "norm": float
# }
INDEX_PATH = Path(__file__).resolve().parent / "thefalse9_index.json"


def _ensure_client_configured() -> None:
    """
    Ensure the Gemini client is configured.

    This loads .env (if present) and configures the API key
    so that app.rag can be used standalone from scripts like
    crawl_thefalse9.py without importing app.llmclient first.
    """
    # Idempotent: calling configure multiple times is safe.
    # We only configure if neither GEMINI_API_KEY nor GOOGLE_API_KEY
    # appears to be set in the environment.
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError(
            "No API key found. Set GEMINI_API_KEY or GOOGLE_API_KEY in your environment or .env file."
        )
    genai.configure(api_key=api_key)


def embed_text(text: str) -> List[float]:
    """
    Get an embedding vector for the given text using a Gemini embedding model.
    """
    _ensure_client_configured()
    result = genai.embed_content(model=EMBEDDING_MODEL, content=text)
    embedding = (
        result.get("embedding")
        if isinstance(result, dict)
        else getattr(result, "embedding", None)
    )
    if embedding is None:
        raise RuntimeError("No embedding returned from Gemini embedding model")
    return [float(x) for x in embedding]


@lru_cache(maxsize=1)
def load_index() -> List[Dict[str, Any]]:
    """
    Load the pre-built index from disk.

    The index must be created offline from thefalse9.com content and saved
    as JSON at INDEX_PATH. Each item should contain:
      - title: article title
      - url: article URL on thefalse9.com
      - text: chunk text
      - embedding: list[float]
      - norm: float (pre-computed L2 norm of the embedding)
    """
    if not INDEX_PATH.exists():
        # No index yet; callers should handle an empty context gracefully.
        return []

    with INDEX_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    normalized: List[Dict[str, Any]] = []
    for item in data:
        emb = item.get("embedding")
        if not isinstance(emb, list) or not emb:
            continue
        norm = float(
            item.get("norm")
            or math.sqrt(sum(float(x) * float(x) for x in emb))
        )
        normalized.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "text": item.get("text", ""),
                "embedding": [float(x) for x in emb],
                "norm": norm,
            }
        )

    return normalized


def _cosine_similarity(
    a: List[float],
    b: List[float],
    norm_b: float,
) -> float:
    norm_a = math.sqrt(sum(x * x for x in a))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (norm_a * norm_b)


def search_context(query: str, k: int = 5) -> List[Dict[str, Any]]:
    """
    Retrieve the top-k most relevant chunks from thefalse9 index.

    Returns a list of dicts with keys: title, url, text.
    If no index exists, this returns an empty list.
    """
    index = load_index()
    if not index:
        return []

    query_emb = embed_text(query)

    scored = []
    for item in index:
        score = _cosine_similarity(query_emb, item["embedding"], item["norm"])
        scored.append((score, item))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    top_items = [item for _, item in scored[:k]]

    return [
        {"title": it["title"], "url": it["url"], "text": it["text"]}
        for it in top_items
    ]


def build_index_from_corpus(
    corpus: List[Dict[str, str]],
    output_path: Optional[Path] = None,
) -> None:
    """
    Utility to incrementally build/update an index file from a corpus of
    thefalse9 articles.

    This is intended to be run offline (e.g., from a separate script).
    `corpus` should be a list of dicts:
      {"title": str, "url": str, "text": str}
    The function appends any new articles to the JSON file at `output_path`
    (or INDEX_PATH by default). Existing URLs are not re-embedded, so each
    article is processed only once.
    """
    target_path = output_path or INDEX_PATH
    existing_records: List[Dict[str, Any]] = []
    if target_path.exists():
        try:
            with target_path.open("r", encoding="utf-8") as f:
                raw_index = json.load(f)
                if isinstance(raw_index, list):
                    existing_records = raw_index
        except Exception as exc:
            print(f"Warning: could not read existing index: {exc}")

    existing_urls = {
        item.get("url")
        for item in existing_records
        if isinstance(item, dict) and item.get("url")
    }

    new_records: List[Dict[str, Any]] = []
    for article in corpus:
        title = article.get("title", "")
        url = article.get("url", "")
        text = article.get("text", "")
        if not text:
            continue
        if url and url in existing_urls:
            continue

        emb = embed_text(text)
        norm = math.sqrt(sum(x * x for x in emb))
        record = {
            "title": title,
            "url": url,
            "text": text,
            "embedding": emb,
            "norm": norm,
        }
        new_records.append(record)
        if url:
            existing_urls.add(url)

    if not new_records:
        return

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(
        json.dumps(existing_records + new_records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
