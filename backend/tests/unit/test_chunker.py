"""Chunker correctness against a real committed transcript plus targeted
synthetic cases. Citation quality is downstream of everything here."""

from app.rag.chunker import (
    build_chunks, chunk_transcript, parse_front_matter, parse_segments,
)
from tests.conftest import load_fixture

SYNTHETIC = """---
guest: Test Guest
title: A test episode
youtube_url: https://www.youtube.com/watch?v=abc123
publish_date: 2024-01-01
keywords:
- growth
---

# A test episode

## Transcript

Test Guest (00:00:05):
First thought about activation metrics and onboarding funnels.

(00:00:40):
Continuation by the same speaker [inaudible 00:00:42] with more detail.

Lenny (00:01:30):
A question from the host about retention.
"""


def test_front_matter_parsed():
    meta, body = parse_front_matter(SYNTHETIC, "test-guest")
    assert meta.guest == "Test Guest"
    assert meta.title == "A test episode"
    assert meta.youtube_url == "https://www.youtube.com/watch?v=abc123"
    assert meta.publish_date == "2024-01-01"
    assert meta.keywords == ["growth"]
    assert "## Transcript" in body


def test_front_matter_missing_is_tolerated():
    meta, body = parse_front_matter("Just text, no front matter.", "some-slug")
    assert meta.slug == "some-slug"
    assert meta.guest == "Some Slug"
    assert body.startswith("Just text")


def test_segments_carry_forward_speaker_and_strip_inaudible():
    _, body = parse_front_matter(SYNTHETIC, "test-guest")
    segments = parse_segments(body)
    assert [s.speaker for s in segments] == ["Test Guest", "Test Guest", "Lenny"]
    assert [s.ts_seconds for s in segments] == [5, 40, 90]
    assert "[inaudible" not in segments[1].text
    # "## Transcript" heading must not be swallowed into a segment as speech
    assert all("## Transcript" not in s.text for s in segments)


def test_chunks_have_monotonic_timestamps_and_content():
    meta, chunks = chunk_transcript(SYNTHETIC, "test-guest")
    assert len(chunks) >= 1
    for c in chunks:
        assert c.start_ts <= c.end_ts
        assert c.token_count > 0
        assert "Test Guest:" in c.content or "Lenny:" in c.content


def test_real_transcript_end_to_end():
    raw = load_fixture("brian-chesky.md")
    meta, chunks = chunk_transcript(raw, "brian-chesky")
    assert meta.guest == "Brian Chesky"
    assert meta.youtube_url and "youtube" in meta.youtube_url
    assert 10 <= len(chunks) <= 80  # ~80KB transcript into ~800-token chunks
    # chunk sizing: no absurdly large chunks (2x target is the hard ceiling
    # only a single oversized segment could hit)
    assert all(c.token_count < 1800 for c in chunks)
    # timestamps increase across chunk boundaries
    starts = [c.start_ts for c in chunks]
    assert starts == sorted(starts)
    # indexes are dense
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_mm_ss_timestamp_variant():
    # 28 of 303 episodes use (MM:SS) instead of (HH:MM:SS)
    raw = (
        "---\nguest: Janna Bastow\n---\n\n## Transcript\n\n"
        "Janna Bastow (00:00):\nA roadmap is a prototype for your strategy.\n\n"
        "Lenny (01:15):\nHow so?\n\n"
        "Janna Bastow (65:30):\nBeyond an hour, minutes keep counting.\n"
    )
    segments = parse_segments(parse_front_matter(raw, "janna-bastow")[1])
    assert [s.ts_seconds for s in segments] == [0, 75, 3930]
    assert [s.speaker for s in segments] == ["Janna Bastow", "Lenny", "Janna Bastow"]


def test_bracket_timestamp_variant():
    # ryan-hoover format: "[00:00:28] Lenny: text on one line"
    raw = (
        "## Transcript\n\n"
        "[00:00:00] Ryan: That flutter in your stomach.\n"
        "[00:28] Lenny: Ryan Hoover is the founder of Product Hunt.\n"
        "[01:00:05] Ryan: Deep into hour one.\n"
    )
    segments = parse_segments(raw)
    assert [s.ts_seconds for s in segments] == [0, 28, 3605]
    assert [s.speaker for s in segments] == ["Ryan", "Lenny", "Ryan"]


def test_bare_speaker_variant_without_timestamps():
    # adriel-frederick format: "Speaker Name:" alone on a line, no timestamps
    raw = (
        "## Transcript\n\n"
        "Adriel Frederick:\nAlgorithms don't understand long term effects.\n\n"
        "Lenny:\nWelcome to the podcast.\n"
    )
    segments = parse_segments(raw)
    assert [s.speaker for s in segments] == ["Adriel Frederick", "Lenny"]
    assert all(s.ts_seconds == 0 for s in segments)


def test_tiny_trailing_chunk_is_folded():
    segments_text = "\n\n".join(
        f"Guest (00:{i:02d}:00):\n" + ("word " * 300) for i in range(4)
    ) + "\n\nGuest (00:59:00):\nshort tail."
    _, body = parse_front_matter("---\nguest: G\n---\n" + segments_text, "g")
    chunks = build_chunks(parse_segments(body))
    assert chunks[-1].content.endswith("short tail.")
    assert chunks[-1].token_count >= 80 or len(chunks) == 1
