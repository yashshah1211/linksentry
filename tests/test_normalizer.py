"""Tests for linksentry.normalizer — unit tests and property-based tests.

Property-based tests use Hypothesis.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from linksentry.normalizer import NormalizerError, normalize

# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Valid hostname labels: 1–63 chars of alphanumerics and hyphens,
# not starting or ending with a hyphen.
_label_strategy = st.from_regex(r"[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?", fullmatch=True)


def valid_url_strategy() -> st.SearchStrategy[str]:
    """Build valid HTTP/HTTPS URL strings from composable parts.

    Composes:
      - scheme: "http" or "https"
      - host:   one or more dot-separated DNS labels (lowercase)
      - optional port: non-default port numbers to exercise port handling
      - optional path: slash-prefixed segments with optional percent-encoded chars
      - optional query: key=value pairs
      - optional fragment: simple alphanumeric fragment

    Generates a wide range of syntactically valid URLs so that
    Property 2 (Normalization Idempotence) is exercised across a large
    and varied input space.
    """

    def _build_url(
        scheme: str,
        labels: list[str],
        port: int | None,
        path_segments: list[str],
        query: str | None,
        fragment: str | None,
    ) -> str:
        host = ".".join(labels)
        netloc = host if port is None else f"{host}:{port}"

        # Build path: always starts with "/"; may have segments.
        if path_segments:
            path = "/" + "/".join(path_segments)
        else:
            path = "/"

        url = f"{scheme}://{netloc}{path}"
        if query:
            url += f"?{query}"
        if fragment:
            url += f"#{fragment}"
        return url

    scheme_st = st.sampled_from(["http", "https"])

    # Host: 1–4 dot-separated labels, each matching a DNS label pattern.
    host_st = st.lists(_label_strategy, min_size=1, max_size=4).filter(
        lambda labels: all(len(l) >= 1 for l in labels)
    )

    # Port: None (omit) or a non-default port between 1 and 65535.
    # Excluding default ports (80 for http, 443 for https) since we include
    # both schemes; normalizer will strip defaults anyway.
    port_st = st.one_of(
        st.none(),
        st.integers(min_value=1, max_value=79),
        st.integers(min_value=81, max_value=442),
        st.integers(min_value=444, max_value=65535),
    )

    # Path segments: URL-safe characters (unreserved + some reserved that
    # are valid in path segments).  Keep it simple to avoid generating
    # URLs that urlparse rejects at the structural level.
    segment_chars = st.text(
        alphabet=st.sampled_from(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "0123456789-._~!$&'()*+,;=:@"
        ),
        min_size=0,
        max_size=20,
    )
    path_st = st.one_of(
        st.just([]),  # empty path → normalizer sets "/"
        st.lists(segment_chars, min_size=1, max_size=4),
    )

    # Query: simple "key=value" or None.
    query_key_val = st.text(
        alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789_"),
        min_size=1,
        max_size=10,
    )
    query_st = st.one_of(
        st.none(),
        st.builds(lambda k, v: f"{k}={v}", query_key_val, query_key_val),
    )

    # Fragment: alphanumeric or None.
    fragment_st = st.one_of(
        st.none(),
        st.text(
            alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789"),
            min_size=1,
            max_size=15,
        ),
    )

    return st.builds(
        _build_url,
        scheme=scheme_st,
        labels=host_st,
        port=port_st,
        path_segments=path_st,
        query=query_st,
        fragment=fragment_st,
    )


# ---------------------------------------------------------------------------
# Property 2 — Normalization Idempotence
# ---------------------------------------------------------------------------


# Feature: link-sentry, Property 2: Normalization Idempotence
@given(valid_url_strategy())
@settings(max_examples=200)
def test_normalization_idempotence(url: str) -> None:
    """normalize(normalize(u)) == normalize(u) for all valid HTTP/HTTPS URLs.

    **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.9**
    """
    first = normalize(url)
    # Only test idempotence when the first normalization succeeds.
    if isinstance(first, NormalizerError):
        return
    second = normalize(first)
    assert second == first, (
        f"Normalization is not idempotent for URL {url!r}:\n"
        f"  normalize(url)          = {first!r}\n"
        f"  normalize(normalize(url)) = {second!r}"
    )


# ---------------------------------------------------------------------------
# Unit tests — example-based
# ---------------------------------------------------------------------------


class TestNormalizeScheme:
    def test_http_scheme_lowercased(self) -> None:
        assert normalize("HTTP://example.com/") == "http://example.com/"

    def test_https_scheme_lowercased(self) -> None:
        assert normalize("HTTPS://Example.COM/") == "https://example.com/"


class TestNormalizeHost:
    def test_host_lowercased(self) -> None:
        result = normalize("https://EXAMPLE.COM/path")
        assert result == "https://example.com/path"

    def test_mixed_case_host(self) -> None:
        result = normalize("http://MyHost.Example.ORG/")
        assert result == "http://myhost.example.org/"


class TestNormalizePort:
    def test_default_http_port_removed(self) -> None:
        result = normalize("http://example.com:80/")
        assert result == "http://example.com/"

    def test_default_https_port_removed(self) -> None:
        result = normalize("https://example.com:443/")
        assert result == "https://example.com/"

    def test_non_default_http_port_preserved(self) -> None:
        result = normalize("http://example.com:8080/")
        assert result == "http://example.com:8080/"

    def test_non_default_https_port_preserved(self) -> None:
        result = normalize("https://example.com:8443/")
        assert result == "https://example.com:8443/"

    def test_http_443_preserved(self) -> None:
        # 443 is not the default for http, so it must be kept.
        result = normalize("http://example.com:443/")
        assert result == "http://example.com:443/"

    def test_https_80_preserved(self) -> None:
        # 80 is not the default for https, so it must be kept.
        result = normalize("https://example.com:80/")
        assert result == "https://example.com:80/"


class TestNormalizePath:
    def test_empty_path_becomes_root(self) -> None:
        result = normalize("https://example.com")
        assert result == "https://example.com/"

    def test_root_path_preserved(self) -> None:
        result = normalize("https://example.com/")
        assert result == "https://example.com/"

    def test_trailing_slash_removed(self) -> None:
        result = normalize("https://example.com/path/")
        assert result == "https://example.com/path"

    def test_multiple_trailing_slashes_removed(self) -> None:
        result = normalize("https://example.com/path///")
        assert result == "https://example.com/path"

    def test_non_trailing_path_preserved(self) -> None:
        result = normalize("https://example.com/a/b/c")
        assert result == "https://example.com/a/b/c"


class TestNormalizePercentEncoding:
    def test_unreserved_char_decoded(self) -> None:
        # %41 is 'A' — an unreserved char; should be decoded.
        result = normalize("https://example.com/%41bc")
        assert result == "https://example.com/Abc"

    def test_reserved_char_hex_uppercased(self) -> None:
        # %2f is '/' — a reserved char; hex should be uppercased.
        result = normalize("https://example.com/a%2fb")
        assert result == "https://example.com/a%2Fb"

    def test_tilde_decoded(self) -> None:
        # %7e is '~' — unreserved; should be decoded.
        result = normalize("https://example.com/%7epath")
        assert result == "https://example.com/~path"

    def test_already_uppercase_hex_unchanged(self) -> None:
        result = normalize("https://example.com/a%2Fb")
        assert result == "https://example.com/a%2Fb"


class TestNormalizeQueryAndFragment:
    def test_query_preserved(self) -> None:
        result = normalize("https://example.com/path?foo=bar&baz=1")
        assert result == "https://example.com/path?foo=bar&baz=1"

    def test_fragment_preserved(self) -> None:
        result = normalize("https://example.com/path#section")
        assert result == "https://example.com/path#section"

    def test_query_and_fragment_preserved(self) -> None:
        result = normalize("https://example.com/?q=hello#top")
        assert result == "https://example.com/?q=hello#top"

    def test_query_parameter_order_preserved(self) -> None:
        result = normalize("https://example.com/?z=1&a=2")
        assert result == "https://example.com/?z=1&a=2"


class TestNormalizeErrors:
    def test_missing_scheme_returns_error(self) -> None:
        result = normalize("example.com/path")
        assert isinstance(result, NormalizerError)

    def test_non_http_scheme_returns_error(self) -> None:
        result = normalize("ftp://example.com/")
        assert isinstance(result, NormalizerError)

    def test_mailto_returns_error(self) -> None:
        result = normalize("mailto:user@example.com")
        assert isinstance(result, NormalizerError)

    def test_empty_string_returns_error(self) -> None:
        result = normalize("")
        assert isinstance(result, NormalizerError)

    def test_no_host_returns_error(self) -> None:
        result = normalize("https:///path")
        assert isinstance(result, NormalizerError)
