"""URL normalizer — pure function, no network I/O."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit


# Characters that are "unreserved" per RFC 3986 and should be
# decoded from percent-encoding rather than kept encoded.
_UNRESERVED = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789"
    "-_.~"
)

_DEFAULT_PORTS: dict[str, int] = {
    "http": 80,
    "https": 443,
}


@dataclass(frozen=True)
class NormalizerError:
    """Returned when the input is not a valid HTTP/HTTPS URL.

    Attributes:
        message: Human-readable description of why normalization failed.
    """

    message: str


def _normalize_percent_encoding(path: str) -> str:
    """Normalize percent-encoded characters in *path*.

    - Decode sequences that encode unreserved characters.
    - Uppercase the hex digits of all remaining encoded sequences.
    """

    def _replace(match: re.Match[str]) -> str:
        hex_digits = match.group(1).upper()
        char = chr(int(hex_digits, 16))

        if char in _UNRESERVED:
            return char

        return f"%{hex_digits}"

    return re.sub(r"%([0-9A-Fa-f]{2})", _replace, path)


def normalize(raw_url: str) -> str | NormalizerError:
    """Return the canonical form of *raw_url*.

    Canonical-form rules:

    1. Scheme is lowercased.
    2. Host is lowercased.
    3. Default ports are removed:
       - 80 for http
       - 443 for https
    4. Non-default ports are preserved.
    5. An empty path becomes "/".
    6. Trailing "/" characters are removed from non-root paths.
    7. Percent-encoding in the path is normalized:
       - unreserved characters are decoded
       - remaining percent-encoded hex digits are uppercased
    8. Query string and fragment are preserved unchanged.

    This function is intended to satisfy normalization idempotence:

        normalize(normalize(url)) == normalize(url)

    for every valid HTTP/HTTPS URL.

    Args:
        raw_url: Raw URL string extracted from Markdown.

    Returns:
        The normalized URL string, or NormalizerError if the input is invalid.
    """

    try:
        parsed = urlsplit(raw_url)
    except Exception as exc:
        return NormalizerError(
            message=f"Failed to parse URL: {exc}"
        )

    if not parsed.scheme:
        return NormalizerError(
            message="URL has no scheme."
        )

    scheme = parsed.scheme.lower()

    if scheme not in _DEFAULT_PORTS:
        return NormalizerError(
            message=(
                f"Unsupported scheme '{parsed.scheme}'; "
                "only http and https are allowed."
            )
        )

    if not parsed.hostname:
        return NormalizerError(
            message="URL has no host."
        )

    host = parsed.hostname.lower()

    # parsed.port can raise ValueError for malformed ports.
    try:
        port = parsed.port
    except ValueError as exc:
        return NormalizerError(
            message=f"Invalid port: {exc}"
        )

    # Rebuild the network location.
    if port is not None and port != _DEFAULT_PORTS[scheme]:
        netloc = f"{host}:{port}"
    else:
        netloc = host

    # Normalize the path.
    path = parsed.path

    if not path:
        path = "/"
    elif path != "/" and path.endswith("/"):
        path = path.rstrip("/") or "/"

    path = _normalize_percent_encoding(path)

    normalized = urlunsplit(
        (
            scheme,
            netloc,
            path,
            parsed.query,
            parsed.fragment,
        )
    )

    return normalized