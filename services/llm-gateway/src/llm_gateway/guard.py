"""Prompt-injection guard for untrusted text (alarm notes, runbook snippets, tool output).

Heuristic, deterministic, explainable: normalised text is matched against instruction-override,
role-hijack, secret-exfiltration and chat-template patterns, including base64-wrapped payloads.
A hit blocks the call (the copilot then falls back to its deterministic answer). The patterns
are evaluated against ``evals/redteam.jsonl`` in CI. NOC wording such as "ignore the flapping
alarm" or "system clock drift" must stay allowed.
"""

from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass

RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        "override",
        re.compile(
            r"\b(ignore|disregard|forget|override|bypass)\b[^.\n]{0,40}\b(previous|prior|above|earlier|all|your|the)\b"
            r"[^.\n]{0,20}\b(instructions?|prompts?|rules|guidelines|directions|context)\b"
        ),
    ),
    ("override", re.compile(r"\bnew (instructions|rules|system prompt)\s*[:\-]")),
    (
        "role",
        re.compile(
            r"\b(you are now|from now on you are|act as|pretend (to be|you are|you have))\b"
            r"[^.\n]{0,40}"
            r"\b(dan|developer mode|jailbr\w*|unrestricted|no (restrictions|rules|limits)"
            r"|evil|admin)\b"
        ),
    ),
    ("role", re.compile(r"\b(developer|god|jailbreak|dan) mode\b")),
    ("role", re.compile(r"\bpretend (you have|there are) no (restrictions|rules|limits)\b")),
    (
        "exfiltration",
        re.compile(
            r"\b(reveal|print|show|repeat|leak|output|tell me)\b[^.\n]{0,30}"
            r"\b(system|hidden|secret|initial)"
            r"\s+(prompt|instructions|message)\b"
        ),
    ),
    (
        "exfiltration",
        re.compile(
            r"\b(api[ _-]?key|password|secret key|access token|jwt)s?\b[^.\n]{0,20}"
            r"\b(respond|reply|print|send|reveal|output)\b|\b(respond|reply|print|send|reveal|output)\b"
            r"[^.\n]{0,30}\b(api[ _-]?key|secret key|access token|credentials)\b"
        ),
    ),
    (
        "tool-hijack",
        re.compile(
            r"\b(you must|always|immediately)\b[^.\n]{0,20}\b(call|use|invoke|run)\b[^.\n]{0,20}"
            r"\b(approve|reject|delete|send)\w*\b"
        ),
    ),
    (
        "tool-hijack",
        re.compile(
            r"\b(approve|close|delete)\b[^.\n]{0,15}\b(ticket|tickets|plan)\b[^.\n]{0,25}"
            r"\b(without|no need for|skip)\b[^.\n]{0,15}\b(approval|review|human|operator)\b"
        ),
    ),
    (
        "template",
        re.compile(
            r"<\|im_(start|end)\|>|<\|(system|assistant|user)\|>|\[/?inst\]|</?\s*(system|context)\s*>"
            r"|^\s*#{2,}\s*system\b|^\s*system\s*(:|override)",
            re.M,
        ),
    ),
]

_B64 = re.compile(r"\b[A-Za-z0-9+/]{16,}={0,2}")
_WS = re.compile(r"\s+")


@dataclass
class Verdict:
    flagged: bool
    reasons: list[str]


def _norm(text: str) -> str:
    return _WS.sub(" ", text).lower()


def _decoded(text: str) -> list[str]:
    out = []
    for m in _B64.finditer(text):
        chunk = m.group(0)
        try:
            raw = base64.b64decode(chunk + "=" * (-len(chunk) % 4), validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError):
            continue
        if raw.isprintable() and " " in raw:
            out.append(raw)
    return out


def check(text: str) -> Verdict:
    reasons: list[str] = []
    candidates = [text, *_decoded(text)]
    for i, cand in enumerate(candidates):
        lowered = cand.lower()
        norm = _norm(cand)
        for name, pat in RULES:
            if pat.search(norm) or (name == "template" and pat.search(lowered)):
                reasons.append(name if i == 0 else f"{name} (base64)")
    return Verdict(bool(reasons), sorted(set(reasons)))
