"""HTTP checker — the sole component that performs network I/O."""

from __future__ import annotations

import time

import requests
import requests.exceptions

from linksentry.classifier import classify
from linksentry.models import CheckResult

DEFAULT_TIMEOUT: float = 10.0  # seconds
DEFAULT_USER_AGENT: str = "LinkSentry/1.0"
MAX_REDIRECTS: int = 10


def check(
    url: str,
    timeout: float = DEFAULT_TIMEOUT,
    user_agent: str = DEFAULT_USER_AGENT,
) -> CheckResult:
    """Check the HTTP status of *url* and return a :class:`~linksentry.models.CheckResult`.

    Issues an HTTP HEAD request first.  If the server does not return a
    valid HTTP response (connection error, timeout, or a non-HTTP-error
    exception), falls back to an HTTP GET request with ``stream=True`` to
    avoid downloading the response body.

    Redirects are followed automatically up to :data:`MAX_REDIRECTS` hops.
    The final status code (after all redirects) is recorded.

    All exceptions are caught; a URL that fails for any reason yields a
    :class:`~linksentry.models.CheckResult` with ``status_code=None``,
    ``response_time_ms=None``, and ``health_label=Broken``.

    Args:
        url: The Normalized_URL to check.
        timeout: Per-request timeout in seconds.  Defaults to
            :data:`DEFAULT_TIMEOUT` (10 s).
        user_agent: Value for the ``User-Agent`` request header.  Defaults
            to :data:`DEFAULT_USER_AGENT`.

    Returns:
        A :class:`~linksentry.models.CheckResult` for *url*.
    """
    start = time.monotonic()

    headers = {"User-Agent": user_agent}
    session = requests.Session()
    session.max_redirects = MAX_REDIRECTS
    session.headers.update(headers)

    status_code: int | None = None
    response_time_ms: int | None = None

    try:
        status_code = _try_head(session, url, timeout)
    except requests.exceptions.TooManyRedirects as exc:
        # Extract status from the last response in the redirect chain.
        status_code = _status_from_redirect_exc(exc)
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        # HEAD failed with a network-level error — fall through to GET.
        status_code = None
    except requests.exceptions.RequestException:
        # Any other requests error on HEAD — fall through to GET.
        status_code = None

    if status_code is None:
        # HEAD did not give us a usable status; try GET.
        try:
            status_code = _try_get(session, url, timeout)
        except requests.exceptions.TooManyRedirects as exc:
            status_code = _status_from_redirect_exc(exc)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            status_code = None
        except requests.exceptions.RequestException:
            status_code = None

    elapsed = time.monotonic() - start
    response_time_ms = int(elapsed * 1000) if status_code is not None else None

    session.close()

    health_label = classify(status_code)
    return CheckResult(
        url=url,
        status_code=status_code,
        response_time_ms=response_time_ms,
        health_label=health_label,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _try_head(session: requests.Session, url: str, timeout: float) -> int:
    """Issue a HEAD request and return the final status code.

    Raises :exc:`requests.exceptions.RequestException` on any failure so
    the caller can decide whether to fall back to GET.
    """
    response = session.head(url, timeout=timeout, allow_redirects=True)
    return response.status_code


def _try_get(session: requests.Session, url: str, timeout: float) -> int:
    """Issue a GET request with ``stream=True`` and return the status code.

    ``stream=True`` prevents the response body from being downloaded.
    The response is closed immediately after reading the status code.

    Raises :exc:`requests.exceptions.RequestException` on any failure.
    """
    response = session.get(url, timeout=timeout, allow_redirects=True, stream=True)
    status = response.status_code
    response.close()
    return status


def _status_from_redirect_exc(exc: requests.exceptions.TooManyRedirects) -> int | None:
    """Extract the HTTP status code from a TooManyRedirects exception."""
    response = getattr(exc, "response", None)
    if response is not None:
        return response.status_code
    return None
