"""LinkSentry Flask application."""

from __future__ import annotations

import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from flask import Flask, render_template, request

from linksentry.checker import check
from linksentry.deduplicator import deduplicate
from linksentry.extractor import extract
from linksentry.models import CheckResult, ResultsSummary
from linksentry.normalizer import NormalizerError, normalize

app = Flask(__name__)

MAX_INPUT_LENGTH: int = 500_000


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/", methods=["GET", "POST"])
def index() -> str:
    """Render the Markdown input form (GET) or run the link-check pipeline (POST)."""
    if request.method == "GET":
        return render_template("index.html")

    # --- POST: run the pipeline ---
    markdown_input: str = request.form.get("markdown_input", "")

    if len(markdown_input) > MAX_INPUT_LENGTH:
        return (
            render_template(
                "index.html",
                error=f"Input exceeds the {MAX_INPUT_LENGTH:,} character limit.",
                markdown_input=markdown_input,
            ),
            400,
        )

    raw_urls = extract(markdown_input)

    normalized_urls: list[str] = []
    for raw in raw_urls:
        result = normalize(raw)
        if isinstance(result, NormalizerError):
            app.logger.warning("Skipping invalid URL %r: %s", raw, result.message)
        else:
            normalized_urls.append(result)

    unique_urls = deduplicate(normalized_urls)

    if not unique_urls:
        return render_template(
            "index.html",
            no_links=True,
            markdown_input=markdown_input,
            summary=ResultsSummary(total=0, healthy=0, redirect=0, broken=0),
            results=[],
        )

    results = _check_urls_concurrently(unique_urls)
    summary = _build_summary(results)

    return render_template(
        "index.html",
        markdown_input=markdown_input,
        results=results,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------


@app.errorhandler(Exception)
def handle_unexpected_error(exc: Exception) -> tuple[str, int]:
    """Log and return a 500 response for any unhandled exception."""
    app.logger.exception("Unhandled exception during request processing")
    return (
        render_template("index.html", error="An unexpected error occurred. Please try again."),
        500,
    )


# ---------------------------------------------------------------------------
# Pipeline helpers
# ---------------------------------------------------------------------------


def _check_urls_concurrently(urls: list[str]) -> list[CheckResult]:
    """Check all *urls* concurrently, preserving input order."""
    max_workers = min(32, len(urls))
    results: dict[str, CheckResult] = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(check, url): url for url in urls}
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                results[url] = future.result()
            except Exception:
                app.logger.exception("Unexpected error checking URL %r", url)
                from linksentry.models import HealthLabel
                results[url] = CheckResult(
                    url=url,
                    status_code=None,
                    response_time_ms=None,
                    health_label=HealthLabel.BROKEN,
                )

    # Restore input order.
    return [results[url] for url in urls]


def _build_summary(results: list[CheckResult]) -> ResultsSummary:
    """Compute aggregate counts from a list of :class:`~linksentry.models.CheckResult`."""
    from linksentry.models import HealthLabel

    healthy = sum(1 for r in results if r.health_label == HealthLabel.HEALTHY)
    redirect = sum(1 for r in results if r.health_label == HealthLabel.REDIRECT)
    broken = sum(1 for r in results if r.health_label == HealthLabel.BROKEN)
    return ResultsSummary(total=len(results), healthy=healthy, redirect=redirect, broken=broken)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    port_str = os.environ.get("PORT", "5000")
    try:
        port = int(port_str)
        if not (1 <= port <= 65535):
            raise ValueError("port out of range")
    except ValueError:
        print(f"Invalid PORT value: {port_str!r}", file=sys.stderr)
        sys.exit(1)

    logging.basicConfig(level=logging.INFO)
    app.run(host="127.0.0.1", port=port)
