"""Transcript parsing and chunking.

Source format (ChatPRD/lennys-podcast-transcripts, one file per episode):

    ---
    guest: Ada Chen Rekhi
    title: ...
    youtube_url: https://www.youtube.com/watch?v=...
    publish_date: 2023-04-21
    ---
    # {title}
    ## Transcript
    Speaker Name (00:00:36):
    paragraph...

    (00:01:21):                <- continuation: same speaker, name omitted
    paragraph...

Strategy: split the body into (speaker, timestamp, text) segments, then merge
consecutive segments into ~TARGET_TOKENS chunks, breaking only on segment
boundaries so a chunk never cuts a speaker mid-thought. Each chunk keeps the
first segment's timestamp — that is what makes YouTube deep-link citations
accurate. Pure functions; no I/O.
"""

import re
from dataclasses import dataclass, field

import yaml

# "Lenny Rachitsky (00:01:21):" or continuation "(00:01:21):". 28 of the 303
# episodes use MM:SS instead of HH:MM:SS, so the hours part is optional.
# Whitespace around the name must be same-line ([ \t], not \s): a \s* here
# would swallow newlines and fuse a paragraph line with the next block's
# timestamp into one bogus header.
_BLOCK_HEADER = re.compile(
    r"^(?P<name>[^\n(]{0,80}?)[ \t]*\((?:(?P<h>\d{1,2}):)?(?P<m>\d{1,2}):(?P<s>\d{2})\):[ \t]*$",
    re.MULTILINE,
)
_INAUDIBLE = re.compile(r"\[inaudible[^\]]*\]", re.IGNORECASE)

# Rare variants (a handful of the 303 episodes):
# B) "[00:00:28] Lenny: text on the same line"  (2- or 3-part timestamp)
_BRACKET_LINE = re.compile(
    r"^\[(?P<a>\d{1,2}):(?P<b>\d{2})(?::(?P<c>\d{2}))?\][ \t]*"
    r"(?P<name>[^\n:]{1,60}):[ \t]*(?P<text>.+)$",
    re.MULTILINE,
)
# C) a bare "Speaker Name:" line with no timestamp, paragraph(s) below
_BARE_SPEAKER = re.compile(r"^(?P<name>[A-Z][^\n:()\[\]]{0,60}):[ \t]*$", re.MULTILINE)

TARGET_TOKENS = 800
MIN_TOKENS = 80  # trailing fragments below this merge into the previous chunk


@dataclass
class EpisodeMeta:
    slug: str
    guest: str
    title: str
    youtube_url: str | None = None
    video_id: str | None = None
    publish_date: str | None = None
    description: str | None = None
    keywords: list[str] = field(default_factory=list)


@dataclass
class Segment:
    speaker: str
    ts_seconds: int
    text: str


@dataclass
class Chunk:
    chunk_index: int
    speaker: str  # dominant speaker by word count
    start_ts: int
    end_ts: int
    content: str
    token_count: int


def estimate_tokens(text: str) -> int:
    # ~1.3 tokens per English word; close enough for chunk sizing.
    return int(len(text.split()) * 1.3)


def parse_front_matter(raw: str, slug: str) -> tuple[EpisodeMeta, str]:
    """Split YAML front matter from the body. Tolerates missing front matter."""
    body = raw
    meta: dict = {}
    if raw.startswith("---"):
        end = raw.find("\n---", 3)
        if end != -1:
            try:
                meta = yaml.safe_load(raw[3:end]) or {}
            except yaml.YAMLError:
                meta = {}
            body = raw[end + 4:]
    keywords = meta.get("keywords") or []
    if not isinstance(keywords, list):
        keywords = [str(keywords)]
    return (
        EpisodeMeta(
            slug=slug,
            guest=str(meta.get("guest", slug.replace("-", " ").title())),
            title=str(meta.get("title", slug)),
            youtube_url=meta.get("youtube_url"),
            video_id=meta.get("video_id"),
            publish_date=str(meta["publish_date"]) if meta.get("publish_date") else None,
            description=meta.get("description"),
            keywords=[str(k) for k in keywords],
        ),
        body,
    )


def parse_segments(body: str) -> list[Segment]:
    """Split the transcript body into speaker/timestamp segments, carrying the
    last-seen speaker across name-less continuation blocks. Falls back to the
    rarer bracket-timestamp and bare-speaker formats when the primary format
    doesn't appear."""
    matches = list(_BLOCK_HEADER.finditer(body))
    segments: list[Segment] = []
    current_speaker = "Unknown"
    for i, m in enumerate(matches):
        name = m.group("name").strip()
        # Headings ("## Transcript") never match; a bare "(00:01:21):" gives name "".
        if name:
            current_speaker = name
        hours = int(m.group("h")) if m.group("h") else 0
        ts = hours * 3600 + int(m.group("m")) * 60 + int(m.group("s"))
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        text = _INAUDIBLE.sub("", body[m.end():end]).strip()
        text = re.sub(r"\s+", " ", text)
        if text:
            segments.append(Segment(speaker=current_speaker, ts_seconds=ts, text=text))
    if segments:
        return segments
    return _parse_bracket_segments(body) or _parse_bare_speaker_segments(body)


def _parse_bracket_segments(body: str) -> list[Segment]:
    """Variant B: '[00:00:28] Lenny: text…' one utterance per line."""
    segments: list[Segment] = []
    for m in _BRACKET_LINE.finditer(body):
        a, b, c = int(m.group("a")), int(m.group("b")), m.group("c")
        ts = a * 3600 + b * 60 + int(c) if c is not None else a * 60 + b
        text = re.sub(r"\s+", " ", _INAUDIBLE.sub("", m.group("text"))).strip()
        if text:
            segments.append(Segment(speaker=m.group("name").strip(), ts_seconds=ts, text=text))
    return segments


def _parse_bare_speaker_segments(body: str) -> list[Segment]:
    """Variant C: bare 'Speaker Name:' lines, no timestamps. Timestamps are 0,
    so citations degrade gracefully to episode-start links."""
    matches = list(_BARE_SPEAKER.finditer(body))
    segments: list[Segment] = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        text = re.sub(r"\s+", " ", _INAUDIBLE.sub("", body[m.end():end])).strip()
        if text:
            segments.append(Segment(speaker=m.group("name").strip(), ts_seconds=0, text=text))
    return segments


def build_chunks(segments: list[Segment], target_tokens: int = TARGET_TOKENS) -> list[Chunk]:
    """Merge segments into chunks of ~target_tokens, breaking on segment
    boundaries only. A single oversized segment becomes its own chunk."""
    chunks: list[Chunk] = []
    buf: list[Segment] = []
    buf_tokens = 0

    def flush() -> None:
        nonlocal buf, buf_tokens
        if not buf:
            return
        by_speaker: dict[str, int] = {}
        for s in buf:
            by_speaker[s.speaker] = by_speaker.get(s.speaker, 0) + len(s.text.split())
        dominant = max(by_speaker, key=by_speaker.get)  # type: ignore[arg-type]
        content = "\n\n".join(f"{s.speaker}: {s.text}" for s in buf)
        chunks.append(
            Chunk(
                chunk_index=len(chunks),
                speaker=dominant,
                start_ts=buf[0].ts_seconds,
                end_ts=buf[-1].ts_seconds,
                content=content,
                token_count=estimate_tokens(content),
            )
        )
        buf, buf_tokens = [], 0

    for seg in segments:
        seg_tokens = estimate_tokens(seg.text)
        if buf and buf_tokens + seg_tokens > target_tokens:
            flush()
        buf.append(seg)
        buf_tokens += seg_tokens
    flush()

    # Fold a tiny trailing chunk into its predecessor.
    if len(chunks) >= 2 and chunks[-1].token_count < MIN_TOKENS:
        last, prev = chunks.pop(), chunks[-1]
        prev.content = f"{prev.content}\n\n{last.content}"
        prev.end_ts = last.end_ts
        prev.token_count = estimate_tokens(prev.content)
    return chunks


def chunk_transcript(raw: str, slug: str) -> tuple[EpisodeMeta, list[Chunk]]:
    meta, body = parse_front_matter(raw, slug)
    return meta, build_chunks(parse_segments(body))
