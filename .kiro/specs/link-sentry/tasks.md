# Implementation Plan: LinkSentry

## Overview

Implement LinkSentry as a self-contained Flask web application that accepts Markdown text, extracts and normalizes HTTP/HTTPS links, checks their HTTP status concurrently, and renders a results table. Implementation follows the pure-logic/I/O separation principle: Extractor, Normalizer, Deduplicator, and Classifier are pure functions; the Checker is the sole network-I/O component. Tasks are ordered from data models → pure logic → checker → Flask route → template/CSS → tests.

## Tasks

- [ ] 1. Scaffold project structure and pin dependencies
  - Create the directory layout: `linksentry/`, `templates/`, `static/`, `tests/`
  - Create `linksentry/__init__.py` (empty)
  - Create `requirements.txt` with pinned versions for `flask`, `requests`, `hypothesis`, `pytest`, `pytest-mock`, and `responses`
  - Create stub files for every module (`app.py`, `linksentry/models.py`, `linksentry/extractor.py`, `linksentry/normalizer.py`, `linksentry/deduplicator.py`, `linksentry/classifier.py`, `linksentry/checker.py`)
  - _Requirements: 10.1, 10.3_

- [ ] 2. Implement data models
  - [ ] 2.1 Implement `HealthLabel` enum and `CheckResult` dataclass in `linksentry/models.py`
    - Define `HealthLabel(str, Enum)` with `HEALTHY = "Healthy"`, `REDIRECT = "Redirect"`, `BROKEN = "Broken"`
    - Define `CheckResult` as a `frozen=True` dataclass with fields `url: str`, `status_code: int | None`, `response_time_ms: int | None`, `health_label: HealthLabel`
    - Define `ResultsSummary` dataclass with `total`, `healthy`, `redirect`, `broken` integer fields
    - _Requirements: 6.1, 7.1, 7.2_

- [ ] 3. Implement pure-logic components
  - [ ] 3.1 Implement `classify()` in `linksentry/classifier.py`
    - Guard chain: `None` or non-`int` → `BROKEN`; 200–299 → `HEALTHY`; 300–399 → `REDIRECT`; all else → `BROKEN`
    - No imports of any HTTP client, socket, or OS networking API
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 8.4_

  - [ ] 3.2 Implement `deduplicate()` in `linksentry/deduplicator.py`
    - Iterate input list; maintain a `set` of seen strings and an output `list`; append each URL only on first occurrence; return output list
    - Case-sensitive, byte-for-byte comparison; empty input returns `[]`
    - No imports of any HTTP client, socket, or OS networking API
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 8.3_

  - [ ] 3.3 Implement `normalize()` in `linksentry/normalizer.py`
    - Use `urllib.parse.urlsplit`/`urlunsplit`; apply canonical-form rules in order: lowercase scheme and host, strip default port (80/http, 443/https), set empty path to `/`, strip trailing slashes from non-root paths, normalize percent-encoding (uppercase hex, decode unreserved chars). Use `urlsplit`/`urlunsplit` (not `urlparse`/`urlunparse`) to avoid the `params` component that causes idempotence failures on URLs containing semicolons.
    - Return `NormalizerError` dataclass for missing/non-http(s) scheme, empty host, or unparseable input
    - Preserve query string and fragment unchanged
    - No imports of any HTTP client, socket, or OS networking API
    - _Requirements: 3.1–3.10, 8.2_

  - [ ] 3.4 Implement `extract()` in `linksentry/extractor.py`
    - Five-pass algorithm: (1) reference definitions, (2) reference usages, (3) inline links, (4) autolinks, (5) bare URLs with trailing-punctuation stripping
    - Collect `(position, url)` pairs across all passes; deduplicate by position; sort by position; return URL strings in order
    - Return only `http`/`https` URLs; never raise; return `[]` for empty or URL-free input
    - No imports of any HTTP client, socket, or OS networking API
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 8.1_

- [ ] 4. Implement the Checker
  - [ ] 4.1 Implement `check()` in `linksentry/checker.py`
    - Define module-level constants: `DEFAULT_TIMEOUT = 10`, `DEFAULT_USER_AGENT = "LinkSentry/1.0"`, `MAX_REDIRECTS = 10`
    - Build a `requests.Session` with `User-Agent` header and `max_redirects`; issue HEAD with `allow_redirects=True`; on failure fall back to GET with `stream=True` (close immediately after headers)
    - Record `start = time.monotonic()` before the first request; compute `response_time_ms = int((time.monotonic() - start) * 1000)` on success; set both to `None` on `Timeout` or `ConnectionError`
    - Catch all other `Exception`; always return a `CheckResult` (null fields + `BROKEN` label on any error)
    - Call `classify(status_code)` from `linksentry.classifier` to set `health_label`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 8.5_

- [ ] 5. Implement the Flask route handler
  - [ ] 5.1 Implement `index()` route in `app.py`
    - Register `GET /` → render empty form; register `POST /` → run the full pipeline
    - POST pipeline: read `markdown_input`, reject with HTTP 400 if `len > 500_000`, call `extract()`, normalize each URL (skip and log `NormalizerError` results), call `deduplicate()`, short-circuit with `no_links=True` if empty, dispatch concurrent checks via `ThreadPoolExecutor(max_workers=min(32, len(unique_urls)))` preserving input order, compute `ResultsSummary`, render `index.html`
    - Register `@app.errorhandler(Exception)` to log full traceback and return HTTP 500 with `text/html` body
    - _Requirements: 1.1, 1.2, 1.4, 1.5, 1.7, 9.1, 9.2, 9.3, 9.4_

  - [ ] 5.2 Add `PORT` env-var support and entry point in `app.py`
    - In `if __name__ == "__main__":` block: read `PORT` env var (default `"5000"`), parse and validate as integer in range 1–65535, print error to stderr and `sys.exit(1)` on invalid value, call `app.run(host="127.0.0.1", port=port)`
    - _Requirements: 10.1, 10.2, 10.4, 10.5, 10.6_

- [ ] 6. Implement the Jinja2 template and CSS
  - [ ] 6.1 Implement `templates/index.html`
    - Single page containing: a `<textarea name="markdown_input">` with `required` attribute, a submit button (disabled during processing via JS), a loading indicator toggled by JS, an inline validation/error message area, and (when results are present) a summary counts section and the Results_Table
    - Results_Table columns in order: URL, Status Code, Response Time (ms), Health; display `—` for null `status_code` or `response_time_ms`; add a CSS class (`healthy` / `redirect` / `broken`) to each row; include a non-color visual indicator (text badge or icon) alongside the color indicator for each health label
    - Display "no links found" message when `no_links=True`
    - _Requirements: 1.1, 1.2, 1.3, 1.6, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 9.4_

  - [ ] 6.2 Implement `static/style.css`
    - Define `.healthy`, `.redirect`, `.broken` row classes with distinct background or border colors (green / yellow / red palette)
    - Each class must also include a non-color distinguisher: a text badge (e.g., `✓ Healthy`, `↪ Redirect`, `✗ Broken`) rendered via a `::before` pseudo-element or an inline element so the table is accessible to color-blind users
    - _Requirements: 7.6_

- [ ] 7. Checkpoint — verify scaffolding and pure-logic components
  - Ensure all stub and implementation files are in place, imports resolve, and `python -m pytest tests/ -k "not checker and not app" --tb=short` passes without network access. Ask the user if any questions arise.

- [x] 8. Write unit and property tests for pure-logic components
  - [x] 8.1 Create `tests/conftest.py` with socket-blocking fixture
    - Define `block_network` as an `autouse=True` session-scoped fixture that monkeypatches `socket.socket` to raise `RuntimeError("Network access is forbidden in unit tests")`
    - _Requirements: 8.6_

  - [ ]* 8.2 Write unit tests for `classifier` in `tests/test_classifier.py`
    - Cover: 200, 204, 299, 300, 301, 399, 400, 404, 500, 599, `None`, 100, 199, 600, non-integer (string, float)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 8.3 Write property test for Classifier (Property 5) in `tests/test_classifier.py`
    - **Property 5: Deterministic Health Classification**
    - Use `@given(st.one_of(st.integers(), st.none(), st.text(), st.floats()))` with `@settings(max_examples=200)`; assert `classify(s) == classify(s)`
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5**

  - [ ]* 8.4 Write unit tests for `deduplicator` in `tests/test_deduplicator.py`
    - Cover: empty list, single element, no duplicates, all duplicates, first-occurrence order preserved, case-sensitive comparison (different capitalizations kept as distinct entries)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 8.5 Write property test for Deduplication Idempotence (Property 3) in `tests/test_deduplicator.py`
    - **Property 3: Deduplication Idempotence**
    - Use `@given(st.lists(st.text()))` with `@settings(max_examples=200)`; assert `deduplicate(deduplicate(L)) == deduplicate(L)`
    - **Validates: Requirements 4.1, 4.2, 4.3**

  - [x] 8.6 Write property test for No Duplicate Output (Property 4) in `tests/test_deduplicator.py`
    - **Property 4: No Duplicate Output**
    - Use `@given(st.lists(st.text()))` with `@settings(max_examples=200)`; assert `len(result) == len(set(result))`
    - **Validates: Requirements 4.1, 4.2, 7.9**

  - [ ]* 8.7 Write unit tests for `normalizer` in `tests/test_normalizer.py`
    - Cover: scheme lowercasing, host lowercasing, default port removal (80/http, 443/https), non-default port preserved, empty path → `/`, trailing slash removal on non-root path, percent-encoding normalization (uppercase hex, decode unreserved), query and fragment preserved, invalid URL → `NormalizerError`
    - _Requirements: 3.1–3.10_

  - [x] 8.8 Write property test for Normalization Idempotence (Property 2) in `tests/test_normalizer.py`
    - **Property 2: Normalization Idempotence**
    - Implement `valid_url_strategy()` custom Hypothesis strategy composing scheme + host + optional path/query/fragment; use `@given(valid_url_strategy())` with `@settings(max_examples=200)`; skip (return) when first `normalize()` returns `NormalizerError`; assert `normalize(normalize(u)) == normalize(u)`
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.9**

  - [ ]* 8.9 Write unit tests for `extractor` in `tests/test_extractor.py`
    - Cover: inline links with and without title, reference links (matched and unmatched), autolinks, bare URLs, trailing-punctuation stripping (`.`, `,`, `)`, `]`, `!`, `?`, `;`, `:`), scheme filtering (mailto, ftp, file, scheme-relative `//`), empty input, input with no HTTP/HTTPS URLs, first-appearance order
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x] 8.10 Write property test for Extraction Purity (Property 1) in `tests/test_extractor.py`
    - **Property 1: Extraction Purity**
    - Use `@given(st.text())` with `@settings(max_examples=200)`; for each URL in `extract(markdown_input)`, assert `url.lower().startswith("http://") or url.lower().startswith("https://")`
    - **Validates: Requirements 2.1, 2.4**

- [ ] 9. Write integration tests for Checker and Flask app
  - [ ] 9.1 Write `tests/test_checker.py` using `responses` mock library
    - Cover: HEAD success (200), HEAD fallback to GET (mock HEAD raises `ConnectionError`), redirect chain ≤ 10 hops (record final status), redirect chain > 10 hops (record 11th-hop status), timeout → null status + `BROKEN`, DNS failure → null status + `BROKEN`, one URL failing does not prevent results for others, `User-Agent` header present on all requests
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8_

  - [ ] 9.2 Write `tests/test_app.py` using Flask test client
    - Cover: GET renders form with `<textarea name="markdown_input">` and submit button; POST with valid Markdown returns 200 with results table; POST with empty body triggers HTML `required` validation (check attribute present); POST exceeding 500,000 chars returns HTTP 400; POST with no extractable URLs shows "no links found" message and empty table with zero counts; results table columns in correct order; null `status_code` displays `—`; null `response_time_ms` displays `—`; row CSS classes match health labels; summary counts sum to total
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 7.1–7.9, 9.3, 9.4_

  - [ ] 9.3 Write PORT environment variable tests in `tests/test_app.py`
    - Cover: valid `PORT` value causes app to listen on that port; invalid `PORT` (non-integer, out-of-range) causes `sys.exit(1)` and prints error to stderr
    - _Requirements: 10.2, 10.4, 10.6_

- [ ] 10. Final checkpoint — full test suite
  - Run `python -m pytest tests/ --tb=short` and verify all tests pass (mocking network in checker/app tests, socket blocked in pure-logic tests). Ask the user if any questions arise.

---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Checkpoints (tasks 7 and 10) ensure incremental validation at natural boundaries
- Property tests use Hypothesis with `max_examples=200` for broad coverage
- The socket-blocking fixture in `conftest.py` (task 8.1) applies `autouse=True`, so it must be created before any pure-logic unit tests are run
- `checker.py` tests must use the `responses` library and must NOT be subject to the socket-blocking fixture — scope the fixture to exclude checker/app tests or place checker tests in a separate conftest scope

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["2.1"] },
    { "id": 1, "tasks": ["3.1", "3.2"] },
    { "id": 2, "tasks": ["3.3", "3.4"] },
    { "id": 3, "tasks": ["4.1"] },
    { "id": 4, "tasks": ["5.1", "5.2"] },
    { "id": 5, "tasks": ["6.1", "6.2"] },
    { "id": 6, "tasks": ["8.1"] },
    { "id": 7, "tasks": ["8.2", "8.3", "8.4", "8.5", "8.6", "8.7", "8.8", "8.9", "8.10"] },
    { "id": 8, "tasks": ["9.1", "9.2"] },
    { "id": 9, "tasks": ["9.3"] }
  ]
}
```
