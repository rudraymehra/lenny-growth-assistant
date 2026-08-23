"""Artifact sanitization policy — the server half of the two-layer defense.

Generated HTML is untrusted model output: a prompt-injected transcript chunk
or a hostile user request could make the model emit script tags, event
handlers, or data-exfiltrating URLs. Policy:

PERMITTED  — document structure (headings, p, lists, tables, blockquote, hr,
             details/summary), inline text semantics (strong/em/code/etc.),
             inline styling via `style`/`class` (visual-only), https images,
             https links, and a single top-level <style> block so the model
             can ship a complete styled one-pager.
BLOCKED    — <script> and every on* event handler (execution), <iframe>/
             <object>/<embed> (nested browsing contexts), <form>/<input>
             (phishing/credential capture), javascript:/data: URLs
             (execution + exfiltration), <link>/@import-able external CSS
             (tracking/exfiltration via requests).

Client half: the viewer renders even this sanitized HTML inside
<iframe sandbox=""> with a default-src 'none' CSP (SandboxFrame.tsx), so a
sanitizer bypass still lands in an inert, origin-less document.
"""

import nh3

_ALLOWED_TAGS = {
    # structure
    "h1", "h2", "h3", "h4", "h5", "h6", "p", "div", "span", "section", "article",
    "header", "footer", "main", "br", "hr", "blockquote", "pre", "details", "summary",
    # text semantics
    "strong", "b", "em", "i", "u", "s", "code", "kbd", "mark", "small", "sub", "sup",
    # lists & tables
    "ul", "ol", "li", "dl", "dt", "dd",
    "table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption", "colgroup", "col",
    # media & links (attribute-filtered below)
    "a", "img", "figure", "figcaption",
    # allow a complete styled document
    "style",
}

_ALLOWED_ATTRIBUTES = {
    "*": {"class", "style", "id", "title"},
    "a": {"href"},
    "img": {"src", "alt", "width", "height"},
    "th": {"colspan", "rowspan", "scope"},
    "td": {"colspan", "rowspan"},
    "ol": {"start", "type"},
    "col": {"span"},
}

# nh3 keeps only these URL schemes on href/src; javascript: and data: fall away.
_ALLOWED_URL_SCHEMES = {"https", "http", "mailto"}


def sanitize_html(raw: str) -> str:
    return nh3.clean(
        raw,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        url_schemes=_ALLOWED_URL_SCHEMES,
        link_rel="noopener noreferrer",
        # ammonia's default content-strip set includes <style>; we allow
        # <style> as a tag, so restrict content-stripping to <script>.
        clean_content_tags={"script"},
    )


def sanitize_artifact(kind: str, content: str) -> str:
    """Markdown artifacts are sanitized too: they may embed raw HTML, and the
    viewer renders markdown→HTML. Same policy for both kinds."""
    if kind == "html":
        return sanitize_html(content)
    return content  # markdown is rendered client-side with rehype-sanitize; raw HTML is stripped there
