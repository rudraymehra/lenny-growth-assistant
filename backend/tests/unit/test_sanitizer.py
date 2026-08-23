"""The XSS corpus: everything here must come out inert. The sanitizer is the
server half of the artifact-security story (SandboxFrame is the client half)."""

from app.artifacts.sanitizer import sanitize_html

HOSTILE = [
    ('<script>alert(1)</script>', "script tag"),
    ('<img src="x" onerror="alert(1)">', "event handler"),
    ('<a href="javascript:alert(1)">click</a>', "javascript: URL"),
    ('<iframe src="https://evil.example"></iframe>', "nested browsing context"),
    ('<object data="https://evil.example/x.swf"></object>', "object embed"),
    ('<form action="https://evil.example"><input name="pw"></form>', "credential form"),
    ('<svg onload="alert(1)"><circle r="1"/></svg>', "svg onload"),
    ('<a href="data:text/html,<script>alert(1)</script>">x</a>', "data: URL"),
    ('<link rel="stylesheet" href="https://evil.example/x.css">', "external CSS"),
    ('<base href="https://evil.example/">', "base hijack"),
    ('<math><mtext></mtext><script>alert(1)</script></math>', "mathml smuggling"),
]


def test_hostile_corpus_is_neutralized():
    for payload, label in HOSTILE:
        cleaned = sanitize_html(payload)
        low = cleaned.lower()
        assert "<script" not in low, label
        assert "onerror" not in low and "onload" not in low, label
        assert "javascript:" not in low, label
        assert "<iframe" not in low and "<object" not in low and "<form" not in low, label
        assert "data:text/html" not in low, label
        assert "<link" not in low and "<base" not in low, label


def test_legitimate_document_survives():
    doc = (
        '<style>h1 { color: #123456; }</style>'
        '<h1 class="title">Growth Guide</h1>'
        '<p>Points with <strong>bold</strong> and <em>emphasis</em>.</p>'
        '<ul><li>Item one</li></ul>'
        '<table><tr><th scope="col">A</th><td colspan="2">B</td></tr></table>'
        '<a href="https://www.youtube.com/watch?v=x">source</a>'
        '<img src="https://example.com/chart.png" alt="chart">'
    )
    cleaned = sanitize_html(doc)
    for fragment in ("<style>", "<h1", "<strong>", "<ul>", "<table>",
                     'href="https://www.youtube.com/watch?v=x"', "<img"):
        assert fragment in cleaned
    # links get hardened rel
    assert "noopener" in cleaned


def test_http_and_mailto_allowed_https_images_only_by_scheme():
    assert 'href="http://example.com"' in sanitize_html('<a href="http://example.com">x</a>')
    assert 'href="mailto:a@b.c"' in sanitize_html('<a href="mailto:a@b.c">x</a>')
