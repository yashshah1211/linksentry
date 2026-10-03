"""Health classifier — pure function, no network I/O."""

from __future__ import annotations

from linksentry.models import HealthLabel


def classify(status_code: int | None) -> HealthLabel:
    """Deterministically map an HTTP status code to a :class:`~linksentry.models.HealthLabel`.

    Returns ``Healthy`` for 2xx, ``Redirect`` for 3xx, and ``Broken``
    for everything else (4xx, 5xx, out-of-range codes, ``None``, and
    non-integer values).  Pure and side-effect-free: identical inputs
    always produce identical outputs.
    """
    if status_code is None or not isinstance(status_code, int):
        return HealthLabel.BROKEN
    if 200 <= status_code <= 299:
        return HealthLabel.HEALTHY
    if 300 <= status_code <= 399:
        return HealthLabel.REDIRECT
    return HealthLabel.BROKEN
