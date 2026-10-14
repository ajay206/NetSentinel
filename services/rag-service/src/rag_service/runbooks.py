from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Runbook:
    id: str
    title: str
    fault_type: str
    tags: tuple[str, ...]
    body: str
    path: str


_FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_TAGS_RE = re.compile(r"\[([^\]]*)\]")


def _parse_front_matter(text: str) -> dict[str, str]:
    match = _FRONT_MATTER_RE.match(text)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def _parse_tags(value: str) -> tuple[str, ...]:
    match = _TAGS_RE.search(value)
    if not match:
        return ()
    inner = match.group(1)
    return tuple(tag.strip() for tag in inner.split(",") if tag.strip())


def parse_runbook(path: str | Path) -> Runbook:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    fields = _parse_front_matter(text)
    if "id" not in fields or not fields["id"]:
        raise ValueError(f"Missing 'id' in runbook front matter: {p}")
    if "title" not in fields or not fields["title"]:
        raise ValueError(f"Missing 'title' in runbook front matter: {p}")
    body = _FRONT_MATTER_RE.sub("", text, count=1)
    return Runbook(
        id=fields["id"],
        title=fields["title"],
        fault_type=fields.get("faultType", ""),
        tags=_parse_tags(fields.get("tags", "")),
        body=body,
        path=str(p),
    )


def load_runbooks(directory: str | Path) -> list[Runbook]:
    d = Path(directory)
    runbooks = [parse_runbook(p) for p in sorted(d.glob("*.md"))]
    return sorted(runbooks, key=lambda r: r.id)
