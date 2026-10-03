"""Link extractor for Markdown text — pure function, no network I/O."""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

# Reference-link definitions: [id]: url  (with optional title on same line)
_RE_REF_DEF = re.compile(
    r"^\s{0,3}\[(?P<label>[^\]]+)\]:\s+(?P<url>https?://\S+?)(?:\s+.*)?$",
    re.MULTILINE | re.IGNORECASE,
)

# Reference-link usages: [text][id] or [text][]
_RE_REF_USE = re.compile(r"\[(?:[^\[\]]*)\]\[(?P<label>[^\]]*)\]")

# Inline links: [text](url) or [text](url "title")
_RE_INLINE = re.compile(
    r"\[(?:[^\[\]]*)\]\(\s*(?P<url>https?://[^\s)\"']+?)(?:\s+[\"'][^\"']*[\"'])?\s*\)"
)

# Autolinks: <http://...> or <https://...>
_RE_AUTOLINK = re.compile(r"<(?P<url>https?://[^>]+)>")

# Bare URLs: http:// or https:// followed by non-whitespace chars
_RE_BARE = re.compile(r"(?P<url>https?://\S+)")

# Trailing punctuation to strip from bare URLs
_TRAILING_PUNCT = frozenset(".,:)!?;]}")


def _strip_trailing_punct(url: str) -> str:
    """Strip trailing punctuation characters from a bare URL match."""
    while url and url[-1] in _TRAILING_PUNCT:
        url = url[:-1]
    return url


def extract(markdown_input: str) -> list[str]:
    """Return all HTTP/HTTPS URLs found in *markdown_input*.

    URLs are returned in order of first appearance.  Duplicate raw URLs
    appear as separate entries (deduplication happens downstream).

    Recognized Markdown syntaxes:

    * Inline links: ``[text](url)`` and ``[text](url "title")``
    * Reference links: ``[text][id]`` with ``[id]: url`` definitions
      (unmatched reference IDs are silently ignored)
    * Autolinks: ``<url>``
    * Bare URLs beginning with ``http://`` or ``https://`` — trailing
      punctuation characters (``.``, ``,``, ``)``, ``]``, ``!``, ``?``,
      ``;``, ``:``, ``}``) are stripped from the end.

    Only URLs with scheme ``http`` or ``https`` are returned
    (Correctness Property 1 — Extraction Purity).

    Args:
        markdown_input: A string of Markdown text.  May be empty.

    Returns:
        A list of raw URL strings in order of first appearance.
        Returns ``[]`` when *markdown_input* contains no HTTP/HTTPS URLs.
        Never raises.
    """
    if not markdown_input:
        return []

    # (position, url) pairs collected across all passes.
    collected: list[tuple[int, str]] = []
    # Positions already claimed so each source character yields ≤1 URL.
    claimed: set[int] = set()

    # ------------------------------------------------------------------
    # Pass 1: Collect reference-link definitions.
    # ------------------------------------------------------------------
    ref_defs: dict[str, str] = {}
    for m in _RE_REF_DEF.finditer(markdown_input):
        label = m.group("label").strip().lower()
        url = m.group("url")
        if label not in ref_defs:
            ref_defs[label] = url

    # ------------------------------------------------------------------
    # Pass 2: Reference-link usages.
    # ------------------------------------------------------------------
    for m in _RE_REF_USE.finditer(markdown_input):
        raw_label = m.group("label").strip()
        # Empty label means use the link text as label (collapsed ref).
        label = raw_label.lower() if raw_label else ""
        url = ref_defs.get(label)
        if url and url.lower().startswith(("http://", "https://")):
            pos = m.start()
            if pos not in claimed:
                claimed.add(pos)
                collected.append((pos, url))

    # ------------------------------------------------------------------
    # Pass 3: Inline links.
    # ------------------------------------------------------------------
    for m in _RE_INLINE.finditer(markdown_input):
        url = m.group("url")
        pos = m.start()
        if pos not in claimed:
            claimed.add(pos)
            collected.append((pos, url))

    # ------------------------------------------------------------------
    # Pass 4: Autolinks.
    # ------------------------------------------------------------------
    for m in _RE_AUTOLINK.finditer(markdown_input):
        url = m.group("url")
        pos = m.start()
        if pos not in claimed:
            claimed.add(pos)
            collected.append((pos, url))

    # ------------------------------------------------------------------
    # Pass 5: Bare URLs (lowest priority — skip positions already claimed).
    # ------------------------------------------------------------------
    for m in _RE_BARE.finditer(markdown_input):
        pos = m.start()
        if pos not in claimed:
            url = _strip_trailing_punct(m.group("url"))
            if url:
                claimed.add(pos)
                collected.append((pos, url))

    # Sort by position and return URL strings only.
    collected.sort(key=lambda pair: pair[0])
    return [url for _, url in collected]
