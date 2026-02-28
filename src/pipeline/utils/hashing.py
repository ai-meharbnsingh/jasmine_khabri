"""Shared text normalization and hashing for filter pipeline."""

import hashlib
import re
import unicodedata

_PUNCT_RE = re.compile(r"[^a-z0-9\s]")
_SPACE_RE = re.compile(r"\s+")


def normalize_title(text: str) -> str:
    """Lowercase, NFD-normalize, strip punctuation, collapse whitespace."""
    nfd = unicodedata.normalize("NFD", text.lower())
    cleaned = _PUNCT_RE.sub(" ", nfd)
    return _SPACE_RE.sub(" ", cleaned).strip()


def compute_title_hash(title: str) -> str:
    """Return SHA-256 hex digest of normalized title."""
    return hashlib.sha256(normalize_title(title).encode("utf-8")).hexdigest()
