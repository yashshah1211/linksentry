"""URL deduplicator — pure function, no network I/O."""

from __future__ import annotations


def deduplicate(urls: list[str]) -> list[str]:
    """Return *urls* with duplicates removed, preserving first-occurrence order.

    Two URLs are considered duplicates if and only if they are identical
    strings (case-sensitive, byte-for-byte comparison).  The earliest
    occurrence of each distinct string is kept; subsequent occurrences
    are discarded.

    This function satisfies two correctness properties:

    * **Deduplication Idempotence** (Property 3): ``deduplicate(deduplicate(L)) == deduplicate(L)``
    * **No Duplicate Output** (Property 4): the returned list contains no two equal strings.

    Args:
        urls: A list of URL strings (typically Normalized_URLs).
              An empty list is returned unchanged.

    Returns:
        A new list containing each distinct string from *urls* exactly
        once, in first-occurrence order.
    """
    seen: set[str] = set()
    result: list[str] = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            result.append(url)
    return result
