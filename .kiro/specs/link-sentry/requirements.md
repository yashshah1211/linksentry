# Requirements Document

## Introduction

LinkSentry is a local Flask web application that accepts Markdown text from a user, extracts all HTTP/HTTPS hyperlinks, normalizes and deduplicates them, checks the HTTP status of each link, and presents a results table showing the URL, HTTP status code, response time, and a health classification (Healthy, Redirect, or Broken).

The application is intentionally small and self-contained: it has no authentication, no database, no cloud infrastructure, and no background processing. Pure logic (extraction, normalization, deduplication, classification) is architecturally separated from network I/O so that the core logic can be unit-tested without any network access.

---

## Glossary

- **App**: The LinkSentry Flask web application.
- **Markdown_Input**: A UTF-8 string of Markdown text submitted by the user via the web form.
- **Extractor**: The component that parses Markdown_Input and returns raw URL strings.
- **Normalizer**: The component that transforms a raw URL string into a canonical form.
- **Deduplicator**: The component that removes duplicate URLs from a list of normalized URLs.
- **Checker**: The component that performs HTTP HEAD (falling back to GET) requests against a URL and records the result.
- **Classifier**: The component that maps an HTTP status code to a Health_Label.
- **Health_Label**: One of three string values — `Healthy`, `Redirect`, or `Broken`.
- **Check_Result**: A data record containing: `url` (string), `status_code` (integer or `null`), `response_time_ms` (integer or `null`), and `health_label` (Health_Label).
- **Results_Table**: The HTML table rendered in the browser showing one row per Check_Result.
- **Normalized_URL**: A URL that has been processed by the Normalizer and is in canonical form.
- **Canonical_Form**: A URL with scheme lowercased, host lowercased, default port removed, path percent-encoding normalized, and trailing slash on root path retained.

---

## Requirements

### Requirement 1: Markdown Input Submission

**User Story:** As a user, I want to paste Markdown text into a web form and submit it, so that the App can extract and check all links in that text.

#### Acceptance Criteria

1. THE App SHALL render a single-page HTML form containing a `<textarea>` for Markdown_Input and a submit button.
2. WHEN the user submits the form with non-empty Markdown_Input, THE App SHALL process the input and render the Results_Table on the same page without navigating away from the current page.
3. IF the user submits the form with an empty Markdown_Input, THEN THE App SHALL re-render the form and display an inline validation message indicating that input is required, and SHALL NOT submit the form to the server.
4. THE App SHALL accept Markdown_Input up to 500,000 characters in length.
5. IF the submitted Markdown_Input exceeds 500,000 characters, THEN THE App SHALL return an HTTP 400 response with a human-readable error message and SHALL NOT process the input.
6. WHILE the App is processing a submitted Markdown_Input, THE App SHALL disable the submit button and display a loading indicator to prevent duplicate submissions.
7. IF the App encounters an internal error while processing Markdown_Input, THEN THE App SHALL display an inline error message indicating that processing failed and SHALL re-enable the submit button.

---

### Requirement 2: Link Extraction

**User Story:** As a user, I want the App to extract all HTTP/HTTPS links from my Markdown text, so that only valid web links are checked.

#### Acceptance Criteria

1. WHEN Markdown_Input is processed, THE Extractor SHALL return every URL whose scheme is `http` or `https` that appears in the Markdown_Input, in the order of first appearance, including duplicate raw URLs as separate entries.
2. THE Extractor SHALL recognize URLs in the following Markdown syntaxes: inline links `[text](url)` and `[text](url "title")`, reference links `[text][id]` with `[id]: url` definitions (unmatched reference IDs are ignored), autolinks `<url>`, and bare URLs beginning with `http://` or `https://` where trailing punctuation characters (`.`, `,`, `)`, `]`, `!`, `?`, `;`, `:`) are stripped from the end of the URL.
3. THE Extractor SHALL return raw URL strings exactly as they appear in the Markdown_Input (after stripping trailing punctuation from bare URLs), without further modification.
4. THE Extractor SHALL NOT return URLs whose scheme is not `http` or `https` (including `mailto:`, `ftp:`, `file:`, and scheme-relative `//` URLs).
5. IF Markdown_Input contains no HTTP/HTTPS URLs, THEN THE Extractor SHALL return an empty list.
6. THE Extractor SHALL NOT perform any network I/O.

**Correctness Property — Extraction Purity:** FOR ALL Markdown_Input values, every URL in the list returned by THE Extractor SHALL have a scheme that is exactly `http` or `https`.

---

### Requirement 3: URL Normalization

**User Story:** As a user, I want extracted URLs to be normalized to a canonical form, so that equivalent URLs are treated as the same link.

#### Acceptance Criteria

1. WHEN a raw URL string is passed to the Normalizer, THE Normalizer SHALL return a Normalized_URL in Canonical_Form.
2. THE Normalizer SHALL convert the URL scheme to lowercase.
3. THE Normalizer SHALL convert the URL host to lowercase.
4. THE Normalizer SHALL remove the port from the URL if the port equals the default port for the scheme (`80` for `http`, `443` for `https`); IF the port is present and does not equal the default port for the scheme, THEN THE Normalizer SHALL preserve the port unchanged.
5. THE Normalizer SHALL normalize percent-encoded characters in the URL path to use uppercase hex digits and decode any percent-encoded characters that correspond to unreserved characters (A–Z, a–z, 0–9, `-`, `_`, `.`, `~`).
6. IF the URL path is empty, THEN THE Normalizer SHALL set the path to `/`.
7. THE Normalizer SHALL preserve the URL query string and fragment without modification, including the original order of query parameters.
8. THE Normalizer SHALL NOT perform any network I/O.
9. IF the URL path ends with one or more trailing `/` characters and the path is not equal to `/`, THEN THE Normalizer SHALL remove the trailing `/` characters from the path.
10. IF the input string passed to the Normalizer is not a syntactically valid URL (i.e., missing scheme, malformed host, or unparseable structure), THEN THE Normalizer SHALL return an error indicating the input is invalid and SHALL NOT return a Normalized_URL.

**Correctness Property — Normalization Idempotence:** FOR ALL syntactically valid URL strings `u`, `Normalizer(Normalizer(u))` SHALL equal `Normalizer(u)`. Normalizing an already-normalized URL SHALL produce the identical Normalized_URL.

---

### Requirement 4: URL Deduplication

**User Story:** As a user, I want duplicate links removed before checking, so that each unique URL is checked exactly once.

#### Acceptance Criteria

1. WHEN a list of Normalized_URLs is passed to the Deduplicator, THE Deduplicator SHALL return a list containing each distinct Normalized_URL exactly once.
2. THE Deduplicator SHALL treat two Normalized_URLs as duplicates if and only if they are identical strings, using case-sensitive, byte-for-byte string comparison.
3. THE Deduplicator SHALL preserve the first-occurrence order of URLs from the input list, retaining the earliest-appearing instance of each duplicate group and discarding all subsequent occurrences.
4. THE Deduplicator SHALL NOT perform any network I/O.
5. WHEN the Deduplicator receives an empty list, THE Deduplicator SHALL return an empty list.

**Correctness Property — Deduplication Idempotence:** FOR ALL lists of Normalized_URLs `L`, `Deduplicator(Deduplicator(L))` SHALL equal `Deduplicator(L)`. Deduplicating an already-deduplicated list SHALL produce the identical list.

**Correctness Property — No Duplicate Output:** FOR ALL Markdown_Input values, the list of URLs passed to the Checker SHALL contain no two identical Normalized_URL strings.

---

### Requirement 5: HTTP Status Checking

**User Story:** As a user, I want each unique link checked for its HTTP status, so that I can see whether it is reachable.

#### Acceptance Criteria

1. WHEN the Checker receives a Normalized_URL, THE Checker SHALL issue an HTTP HEAD request to that URL with a timeout that is configurable per-request and defaults to 10 seconds.
2. IF the server does not respond to the HEAD request with a valid HTTP response within the configured timeout, THEN THE Checker SHALL retry using an HTTP GET request to the same URL with the same configured timeout.
3. THE Checker SHALL follow HTTP redirects automatically up to a maximum of 10 hops and SHALL record the final HTTP status code after all redirects have been followed; IF the redirect count exceeds 10 hops, THE Checker SHALL stop following redirects and record the status code of the response at the 11th hop as the final status code.
4. THE Checker SHALL record the elapsed time in milliseconds from the moment the first request is initiated to the moment the final response headers are received, as a non-negative integer.
5. IF the Checker does not receive a response within the configured timeout on both the HEAD and GET attempts, THEN THE Checker SHALL record a `null` status_code, a `null` response_time_ms, and SHALL set the health_label to `Broken`.
6. IF the Checker encounters a network error (DNS resolution failure, connection refused, or TLS handshake error) on a request, THEN THE Checker SHALL record a `null` status_code, a `null` response_time_ms, and SHALL set the health_label to `Broken`.
7. THE Checker SHALL set a `User-Agent` request header on all outbound requests to a non-empty string identifying the App.
8. THE Checker SHALL check each URL independently; a failure on one URL SHALL NOT prevent the Checker from issuing requests for the remaining URLs.

---

### Requirement 6: Health Classification

**User Story:** As a user, I want each checked URL labeled as Healthy, Redirect, or Broken, so that I can quickly identify problem links.

#### Acceptance Criteria

1. WHEN the Classifier receives an HTTP status code, THE Classifier SHALL return a Health_Label according to the following mapping:
   - Status codes 200–299 → `Healthy`
   - Status codes 300–399 → `Redirect`
   - Status codes 400–599 → `Broken`
2. IF the Classifier receives a `null` status code (timeout or network error), THEN THE Classifier SHALL return `Broken`.
3. IF the Classifier receives an integer status code outside the range 200–599 (inclusive), THEN THE Classifier SHALL return `Broken`.
4. THE Classifier SHALL NOT perform any network I/O.
5. IF the Classifier receives a non-integer, non-null value as a status code, THEN THE Classifier SHALL return `Broken`.

**Correctness Property — Deterministic Status Classification:** FOR ALL integer status codes `s`, calling `Classifier(s)` multiple times SHALL return the same Health_Label on every call. The mapping from status code to Health_Label is a pure, side-effect-free function.

---

### Requirement 7: Results Display

**User Story:** As a user, I want to see a table of results for all checked links, so that I can review the status of each URL at a glance.

#### Acceptance Criteria

1. WHEN link checking is complete, THE App SHALL render a Results_Table containing one row per Check_Result, with rows ordered in the same sequence as the deduplicated URL list passed to the Checker.
2. THE Results_Table SHALL contain the following columns in order: URL, Status Code, Response Time (ms), Health.
3. THE App SHALL display the Normalized_URL (not the raw URL) in the URL column.
4. WHEN a status_code is `null`, THE App SHALL display `—` in the Status Code column.
5. WHEN a response_time_ms is `null`, THE App SHALL display `—` in the Response Time (ms) column.
6. THE App SHALL style each Results_Table row with a distinct visual indicator corresponding to its Health_Label: a green indicator for `Healthy`, a yellow indicator for `Redirect`, and a red indicator for `Broken`, where each indicator is visually distinguishable from the others without relying solely on color.
7. THE App SHALL display the total count of checked URLs as a non-negative integer above the Results_Table.
8. THE App SHALL display the count of `Healthy`, `Redirect`, and `Broken` URLs as three separate labeled counts above the Results_Table, where the three counts sum to the total count of checked URLs.
9. THE Results_Table SHALL contain no two rows with the same Normalized_URL.

---

### Requirement 8: Architectural Separation of Logic and I/O

**User Story:** As a developer, I want the pure logic components (Extractor, Normalizer, Deduplicator, Classifier) to have no dependency on network I/O, so that they can be unit-tested without any network access.

#### Acceptance Criteria

1. THE Extractor SHALL be implemented as a pure function with no imports of or calls to any HTTP client library, socket library, or OS networking API.
2. THE Normalizer SHALL be implemented as a pure function with no imports of or calls to any HTTP client library, socket library, or OS networking API.
3. THE Deduplicator SHALL be implemented as a pure function with no imports of or calls to any HTTP client library, socket library, or OS networking API.
4. THE Classifier SHALL be implemented as a pure function with no imports of or calls to any HTTP client library, socket library, or OS networking API.
5. THE Checker SHALL be the sole component that performs network I/O, and THE Checker SHALL accept the Normalized_URL as its only required input parameter; all other parameters (e.g., timeout, User-Agent) SHALL have documented defaults.
6. WHEN running the unit test suite for the Extractor, Normalizer, Deduplicator, and Classifier, THE App SHALL complete all tests without establishing any network connections.

---

### Requirement 9: Error Handling and Resilience

**User Story:** As a user, I want the App to handle unexpected errors gracefully, so that a single bad URL or server error does not crash the application.

#### Acceptance Criteria

1. IF an unhandled exception occurs during link checking for a single URL, THEN THE App SHALL record that URL with a `null` status_code, a `null` response_time_ms, and a health_label of `Broken`, and SHALL continue processing the remaining URLs without interruption.
2. IF an unhandled exception occurs outside of per-URL checking (e.g., during extraction or normalization), THEN THE App SHALL return an HTTP 500 response with a human-readable error message in the response body and SHALL log the full exception stack trace to the server console.
3. THE App SHALL return all HTTP error responses with a `Content-Type` of `text/html` and a non-empty human-readable body describing the nature of the error.
4. IF the Markdown_Input submitted by the user contains no extractable URLs, THEN THE App SHALL display a message to the user indicating that no links were found and SHALL render an empty Results_Table with zero counts in the summary.

---

### Requirement 10: Local Deployment

**User Story:** As a developer, I want to run LinkSentry on my local machine with a single command, so that I can use it without any cloud infrastructure or installation complexity.

#### Acceptance Criteria

1. THE App SHALL be startable with the single command `flask run` or `python app.py` executed from the project root directory, with no additional configuration steps required beyond installing declared dependencies.
2. THE App SHALL listen on `localhost` port `5000` by default when no `PORT` environment variable is set.
3. THE App SHALL declare all Python dependencies with pinned version numbers in a `requirements.txt` file located at the project root.
4. WHERE the environment variable `PORT` is set to a valid port number between 1 and 65535 (inclusive), THE App SHALL listen on the port specified by `PORT` instead of `5000`.
5. THE App SHALL start and serve the input form within 5 seconds of the start command being issued, measured on a machine with a standard developer configuration (at least 8 GB RAM, active internet connection, and dependencies pre-installed).
6. IF the environment variable `PORT` is set to a value that is not a valid port number (not an integer in the range 1–65535), THEN THE App SHALL exit with a non-zero exit code and SHALL print an error message to the console indicating the invalid port value.
