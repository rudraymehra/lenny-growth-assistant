#!/usr/bin/env bash
# Fetch the Lenny's Podcast transcript dataset (knowledge base source).
# Pinned to a known-good commit so ingestion is reproducible; pass --latest
# to track the repository head instead.
set -euo pipefail

REPO_URL="https://github.com/ChatPRD/lennys-podcast-transcripts.git"
PINNED_SHA="be8ab89a890a833cbba2c892178f823fff178c65"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT_DIR/data/transcripts"

if [[ -d "$DEST/episodes" ]]; then
  echo "Transcripts already present at $DEST ($(ls "$DEST/episodes" | wc -l | tr -d ' ') episodes) — skipping clone."
  echo "Delete the directory and re-run to re-fetch."
  exit 0
fi

mkdir -p "$ROOT_DIR/data"
echo "Cloning transcript dataset (shallow) ..."
git clone --depth 1 "$REPO_URL" "$DEST"

if [[ "${1:-}" != "--latest" ]]; then
  # Best-effort pin: fetch the pinned commit if the shallow head moved past it.
  ( cd "$DEST" \
    && git fetch --depth 1 origin "$PINNED_SHA" 2>/dev/null \
    && git checkout -q "$PINNED_SHA" \
    && echo "Pinned to $PINNED_SHA" ) \
  || echo "Could not pin to $PINNED_SHA; using repository head $(cd "$DEST" && git rev-parse --short HEAD)."
fi

echo "Done: $(ls "$DEST/episodes" | wc -l | tr -d ' ') episodes in $DEST/episodes"
