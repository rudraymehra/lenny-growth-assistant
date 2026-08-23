"""Intent routing for the local engine — deterministic and documented."""

import pytest

from app.engines.intents import classify


@pytest.mark.parametrize("text,expected", [
    ("How does Brian Chesky think about founder mode?", "chat"),
    ("What do guests say about pricing experiments?", "chat"),
    ("Write a Ship 30 essay about activation metrics", "essay"),
    ("write an essay on retention", "essay"),
    ("Draft an article on onboarding", "essay"),
    ("Turn this into a blog post", "essay"),
    ("Make an HTML one-pager summarizing this", "artifact_html"),
    ("Create a landing page for this idea", "artifact_html"),
    ("build a web page with these tips", "artifact_html"),
    ("Give me a checklist for user interviews", "artifact_markdown"),
    ("Create a template for PRD reviews", "artifact_markdown"),
    ("make a cheat sheet of growth loops", "artifact_markdown"),
])
def test_classification(text: str, expected: str):
    assert classify(text) == expected


def test_essay_wins_over_document_words():
    # an essay request that also mentions markdown stays an essay
    assert classify("Write an essay as a markdown document") == "essay"
