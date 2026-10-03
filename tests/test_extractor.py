"""Tests for linksentry.extractor."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from linksentry.extractor import extract


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------

# Feature: link-sentry, Property 1: Extraction Purity
@given(st.text())
@settings(max_examples=200)
def test_extraction_purity(markdown_input: str) -> None:
    """Property 1: Extraction Purity.

    Every URL returned by extract() must start with 'http://' or 'https://'.

    Validates: Requirements 2.1, 2.4
    """
    urls = extract(markdown_input)
    for url in urls:
        assert url.lower().startswith("http://") or url.lower().startswith("https://"), (
            f"extract() returned a URL with an unexpected scheme: {url!r}"
        )
