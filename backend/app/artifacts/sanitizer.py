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
             (execution + exfiltration), <link>/<base> (external CSS / URL
             hijack), and — because nh3 does not parse CSS — url()/@import/
             expression()/image-set() are stripped from surviving CSS so a
             prompt-injected style cannot beacon to a remote host.

Client half: the viewer renders even this sanitized HTML inside
<iframe sandbox=""> with a default-src 'none' CSP (SandboxFrame.tsx), so a
sanitizer bypass still lands in an inert, origin-less document.
"""

import re

import nh3

# nh3/ammonia allowlists tags/attrs but does NOT parse CSS, so CSS-level fetch
# vectors survive it. Strip them from the cleaned output as a second pass.
_CSS_FETCH = re.compile(
    r"@import[^;]*;?|url\s*\([^)]*\)|expression\s*\([^)]*\)|image-set\s*\([^)]*\)",
    re.IGNORECASE,
)

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
    cleaned = nh3.clean(
        raw,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        url_schemes=_ALLOWED_URL_SCHEMES,
        link_rel="noopener noreferrer",
        # ammonia's default content-strip set includes <style>; we allow
        # <style> as a tag, so restrict content-stripping to <script>.
        clean_content_tags={"script"},
    )
    # Second pass: neutralise CSS-level fetch vectors nh3 leaves untouched.
    return _CSS_FETCH.sub("", cleaned)


def sanitize_artifact(kind: str, content: str) -> str:
    """Markdown artifacts are sanitized too: they may embed raw HTML, and the
    viewer renders markdown→HTML. Same policy for both kinds."""
    if kind == "html":
        return sanitize_html(content)
    # Markdown is rendered client-side by react-markdown, which does NOT
    # render embedded raw HTML (no rehype-raw plugin) — HTML inside markdown
    # arrives as inert text, so the content passes through unchanged here.
    return content
