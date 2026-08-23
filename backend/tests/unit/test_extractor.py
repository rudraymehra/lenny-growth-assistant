"""ArtifactStreamFilter: fence content never leaks into chat text, artifacts
are captured intact, and split-across-deltas markers are handled."""

from app.artifacts.extractor import ArtifactStreamFilter

DOC = 'Here is your page.\n```artifact:html title="Growth One-Pager"\n<h1>Hi</h1>\n<p>Body</p>\n```\nDone!'


def _run(pieces: list[str]) -> tuple[str, ArtifactStreamFilter]:
    f = ArtifactStreamFilter()
    visible = "".join(f.feed(p) for p in pieces)
    visible += f.flush()
    return visible, f


def test_single_delta():
    visible, f = _run([DOC])
    assert "Here is your page." in visible
    assert "Done!" in visible
    assert "<h1>" not in visible
    assert len(f.artifacts) == 1
    a = f.artifacts[0]
    assert a.kind == "html"
    assert a.title == "Growth One-Pager"
    assert a.content == "<h1>Hi</h1>\n<p>Body</p>"


def test_marker_split_across_every_boundary():
    # brutal: feed one character at a time
    visible, f = _run(list(DOC))
    assert "<h1>" not in visible
    assert "Done!" in visible
    assert len(f.artifacts) == 1
    assert f.artifacts[0].content == "<h1>Hi</h1>\n<p>Body</p>"


def test_markdown_artifact_without_title():
    text = "```artifact:markdown\n# Essay\n\nBody text.\n```"
    visible, f = _run([text[:10], text[10:25], text[25:]])
    assert visible.strip() == ""
    assert f.artifacts[0].kind == "markdown"
    assert f.artifacts[0].title == ""
    assert f.artifacts[0].content.startswith("# Essay")


def test_unterminated_fence_is_recovered_on_flush():
    visible, f = _run(["preamble\n```artifact:markdown title=\"T\"\npartial content"])
    assert "preamble" in visible
    assert "partial content" not in visible
    assert len(f.artifacts) == 1
    assert f.artifacts[0].content == "partial content"


def test_plain_text_with_ordinary_code_fence_passes_through():
    text = "Use this:\n```python\nprint('hi')\n```\nthe end"
    visible, f = _run([text])
    assert visible == text
    assert f.artifacts == []
