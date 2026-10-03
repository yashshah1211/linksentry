# LinkSentry

LinkSentry is a lightweight Markdown link auditor built with Kiro.

Paste Markdown text into the web app and LinkSentry will:

- extract HTTP/HTTPS links
- normalize URLs
- remove duplicates
- check each link concurrently
- classify links as Healthy, Redirect, or Broken
- show HTTP status codes and response times

The project was built for the Kiro University Challenge using spec-driven development, Steering, Hooks, property-based testing, Powers, MCP, and a custom Kiro agent.

---

## Demo

<!-- Add your demo video link here after recording -->

**Demo video:** Coming soon

### Example

Input:

```markdown
# Useful links

[Example](https://example.com)
[GitHub](https://github.com)
[Broken](https://example.invalid)

https://github.com
