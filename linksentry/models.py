"""Data models for LinkSentry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class HealthLabel(str, Enum):
    """Classification of a checked URL's health.

    Inheriting from ``str`` allows Jinja2 to render the value directly
    and lets equality comparisons against plain strings work naturally.
    """

    HEALTHY = "Healthy"
    REDIRECT = "Redirect"
    BROKEN = "Broken"


@dataclass(frozen=True)
class CheckResult:
    """Immutable record of a single URL check.

    Attributes:
        url: The Normalized_URL that was checked.
        status_code: Final HTTP status code, or ``None`` on failure.
        response_time_ms: Elapsed milliseconds from first request to
            final response headers, or ``None`` on failure.
        health_label: Health classification derived from ``status_code``.
    """

    url: str
    status_code: int | None
    response_time_ms: int | None
    health_label: HealthLabel


@dataclass
class ResultsSummary:
    """Aggregate counts for the results table header.

    Attributes:
        total: Total number of URLs checked.
        healthy: Count of URLs classified as Healthy.
        redirect: Count of URLs classified as Redirect.
        broken: Count of URLs classified as Broken.
    """

    total: int
    healthy: int
    redirect: int
    broken: int
