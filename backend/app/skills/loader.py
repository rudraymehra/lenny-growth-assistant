"""Loads SKILL.md files so both engines share one source of truth:
the Claude Agent SDK discovers them from workspace/.claude/skills/ natively,
while the local engine embeds the same instructions into its compact prompt."""

import re
from functools import lru_cache
from pathlib import Path

WORKSPACE_DIR = Path(__file__).resolve().parents[2] / "workspace"
SKILLS_DIR = WORKSPACE_DIR / ".claude" / "skills"

_FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


@lru_cache
def load_skill_body(name: str) -> str:
    """SKILL.md body with front matter stripped; raises if the skill is missing
    (a packaging error we want loudly at startup, not silently at request time)."""
    path = SKILLS_DIR / name / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    return _FRONT_MATTER.sub("", text).strip()


def ship30_prompt() -> str:
    return load_skill_body("ship-30-essay")
