from __future__ import annotations

from dataclasses import dataclass

from .runbooks import Runbook


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    runbook_id: str
    title: str
    section: str
    text: str
    fault_type: str


def _split_long(text: str, max_chars: int, overlap: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if current and len(current) + 1 + len(para) > max_chars:
            chunks.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        chunks.append(current)
    if not chunks:
        return [text]
    result: list[str] = []
    for chunk in chunks:
        if len(chunk) <= max_chars:
            result.append(chunk)
            continue
        start = 0
        while start < len(chunk):
            end = start + max_chars
            result.append(chunk[start:end])
            if end >= len(chunk):
                break
            start = end - overlap
    return result


def chunk_runbook(rb: Runbook, max_chars: int = 800, overlap: int = 100) -> list[Chunk]:
    # Split on level-2 headings; text before the first one is the "Overview" preamble.
    sections = ("## Overview\n" + rb.body).split("\n## ")
    chunks: list[Chunk] = []
    idx = 0
    for section in sections:
        section = section.strip()
        if not section:
            continue
        lines = section.split("\n", 1)
        heading = lines[0].strip()
        content = lines[1].strip() if len(lines) > 1 else ""
        heading = heading.removeprefix("## ").strip()
        content = "\n".join(ln for ln in content.splitlines() if not ln.startswith("# "))
        content = content.strip()
        if not content:
            continue
        # The id and tags go into the heading line so BM25 can match exact IDs/tags;
        # snippets drop this first line.
        tags = ", ".join(rb.tags)
        prefix = f"{rb.title} — {heading} ({rb.id}; {tags})\n"
        full_text = prefix + content
        for piece in _split_long(full_text, max_chars, overlap):
            chunks.append(
                Chunk(
                    chunk_id=f"{rb.id}#{idx}",
                    runbook_id=rb.id,
                    title=rb.title,
                    section=heading,
                    text=piece,
                    fault_type=rb.fault_type,
                )
            )
            idx += 1
    return chunks
