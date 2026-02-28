"""Shared text normalization and hashing for filter pipeline."""

import re

_PUNCT_RE = re.compile(r"[^a-z0-9\s]")
_SPACE_RE = re.compile(r"\s+")


def normalize_title(text: str) -> str:
    """Lowercase, NFD-normalize, strip punctuation, collapse whitespace."""
    raise NotImplementedError


def compute_title_hash(title: str) -> str:
    """Return SHA-256 hex digest of normalized title."""
    raise NotImplementedError
