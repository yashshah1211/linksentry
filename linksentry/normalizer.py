"""URL normalizer — pure function, no network I/O."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

# Characters that are "unreserved" per RFC 3986 and should be
# decoded from percent-encoding rather than kept encoded.
_UNRESERVED = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789"
    "-_.~"
)

_DEFAULT_PORTS: dict[str, int] = {"http": 80, "https": 443}


@dataclass(frozen=True)
class NormalizerError:
    """Returned when the input is not a valid HTTP/HTTPS URL.

    Attributes:
        message: Human-readable description of why normalization failed.
    """

    message: str


def _normalize_percent_encoding(path: str) -> str:
    """Normalize percent-encoded characters in *path*.

    * Decodes sequences that encode unreserved characters (RFC 3986 §2.3).
    * Uppercases the hex digits of all remaining encoded sequences.
    """

    def _replace(match: re.Match[str]) -> str:
        hex_digits = match.group(1).upper()
        char = chr(int(hex_digits, 16))
        if char in _UNRESERVED:
            return char
        return f"%{hex_digits}"

    return re.sub(r"%([0-9A-Fa-f]{2})", _replace, path)


def normalize(raw_url: str) -> str | NormalizerError:
    """Return the Canonical Form of *raw_url*.

    Canonical Form rules applied in order:

    1. Scheme lowercased.
    2. Host lowercased.
    3. Default port removed (80 for http, 443 for https); non-default
       ports are preserved unchanged.
    4. Empty path set to ``/``.
    5. Trailing slashes stripped from non-root paths.
    6. Percent-encoding in the path normalized (unreserved chars decoded;
       hex digits of remaining sequences uppercased).
    7. Query string and fragment preserved without modification (including
       original parameter order).

    This function satisfies **Normalization Idempotence** (Property 2):
    ``normalize(normalize(u)) == normalize(u)`` for all valid *u*.

    Args:
        raw_url: A raw URL string extracted from Markdown text.

    Returns:
        A normalized URL string, or a :class:`NormalizerError` if *raw_url*
        is not a syntactically valid HTTP/HTTPS URL (missing scheme,
        non-http(s) scheme, empty host, or unparseable structure).
    """
    try:
        parsed = urlparse(raw_url)
    except Exception as exc:  # urlparse rarely raises, but be safe
        return NormalizerError(message=f"Failed to parse URL: {exc}")

    if not parsed.scheme:
        return NormalizerError(message="URL has no scheme.")
    if parsed.scheme.lower() not in _DEFAULT_PORTS:
        return NormalizerError(
            message=f"Unsupported scheme '{parsed.scheme}'; only http and https are allowed."
        )
    if not parsed.hostname:
        return NormalizerError(message="URL has no host.")

    scheme = parsed.scheme.lower()
    host = parsed.hostname.lower()  # already excludes port

    # Rebuild netloc: include port only when it is non-default.
    port = parsed.port
    if port is not None and port != _DEFAULT_PORTS[scheme]:
        netloc = f"{host}:{port}"
    else:
        netloc = host

    # Normalise path.
    path = parsed.path
    if not path:
        path = "/"
    elif path != "/" and path.endswith("/"):
        path = path.rstrip("/") or "/"
    path = _normalize_percent_encoding(path)

    normalized = urlunparse((scheme, netloc, path, parsed.params, parsed.query, parsed.fragment))
    return normalized
