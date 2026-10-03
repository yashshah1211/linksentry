# LinkSentry Engineering Guidelines

## Scope
- Implement only functionality defined in the approved LinkSentry spec.
- Keep the application intentionally small.
- Do not add authentication, databases, accounts, cloud infrastructure, AI APIs, Docker, CI/CD, or unrelated features.

## Python
- Use Python 3.11+.
- Add type hints to functions.
- Prefer small functions with one responsibility.
- Keep dependencies minimal and pinned.

## Architecture
- Pure business logic must remain separate from network I/O.
- Only checker.py may perform HTTP/network operations.
- Pure modules must not import requests or other networking libraries.

## Networking
- Every HTTP request must use a timeout.
- Never disable TLS certificate verification.
- Catch specific request exceptions.
- Preserve the HEAD to GET fallback specified in the design.
- Avoid downloading response bodies unnecessarily.

## Testing
- Use pytest for tests.
- Use Hypothesis for property-based testing.
- Property-based tests for pure logic must not access the network.
- Preserve the correctness properties defined in the LinkSentry spec.

## Development
- Prefer the simplest implementation that satisfies the requirements.
- Do not redesign working code without a requirement-driven reason.
- Do not implement optional tasks unless explicitly requested.