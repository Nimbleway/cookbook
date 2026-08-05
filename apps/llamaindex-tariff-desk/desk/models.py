"""One place to configure the LlamaIndex models.

Anthropic for the LLM (normalization and response synthesis), OpenAI for
embeddings — Anthropic has no embeddings API, and local HuggingFace embeddings
would add ~2GB of torch to a cookbook that should install in a minute.

Both are overridable by env var so a reader can swap either without touching code.
"""

from __future__ import annotations

import os

DEFAULT_LLM = "claude-sonnet-5"
DEFAULT_EMBED = "text-embedding-3-small"


def configure_models(require_embeddings: bool = True) -> None:
    """Set Settings.llm and Settings.embed_model. Idempotent.

    Assign without reading first: `Settings.llm` is a lazy property that resolves
    LlamaIndex's *default* provider (OpenAI) on access, so merely inspecting it
    raises ImportError when `llama-index-llms-openai` isn't installed — which it
    isn't here, because the LLM is Anthropic.
    """
    from llama_index.core import Settings

    _set_llm(Settings)
    # These documents are structured JSON answers plus a Sources list, so they chunk
    # badly at the 1024 default — a duty table split mid-array loses the association
    # between a rate and its instrument.
    Settings.chunk_size = int(os.environ.get("DESK_CHUNK_SIZE", "2048"))
    Settings.chunk_overlap = 128
    if require_embeddings:
        _set_embeddings(Settings)


def _set_llm(Settings) -> None:
    from llama_index.llms.anthropic import Anthropic

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set — needed for question normalization and "
            "for writing answers from retrieved facts."
        )
    Settings.llm = Anthropic(
        model=os.environ.get("DESK_LLM_MODEL", DEFAULT_LLM),
        max_tokens=2048,
    )


def _set_embeddings(Settings) -> None:
    from llama_index.embeddings.openai import OpenAIEmbedding

    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not set — needed to embed the corpus. Every agent run "
            "works without it; only the index does not."
        )
    Settings.embed_model = OpenAIEmbedding(
        model=os.environ.get("DESK_EMBED_MODEL", DEFAULT_EMBED)
    )
