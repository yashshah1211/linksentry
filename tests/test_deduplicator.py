"""Tests for linksentry.deduplicator."""

from hypothesis import given, settings
from hypothesis import strategies as st

from linksentry.deduplicator import deduplicate


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------

# Feature: link-sentry, Property 3: Deduplication Idempotence
@given(st.lists(st.text()))
@settings(max_examples=200)
def test_deduplication_idempotence(url_list: list[str]) -> None:
    """Deduplicating an already-deduplicated list must return the identical list.

    Validates: Requirements 4.1, 4.2, 4.3
    """
    once = deduplicate(url_list)
    twice = deduplicate(once)
    assert once == twice


# Feature: link-sentry, Property 4: No Duplicate Output
@given(st.lists(st.text()))
@settings(max_examples=200)
def test_no_duplicate_output(url_list: list[str]) -> None:
    """The output of deduplicate() must contain no two equal elements.

    Validates: Requirements 4.1, 4.2, 7.9
    """
    result = deduplicate(url_list)
    assert len(result) == len(set(result))
