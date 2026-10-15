"""PII redaction for prompts, completions and logs.

Default engine: deterministic regex recognisers tuned for NOC text (they must not touch site,
cell, link, alarm or runbook ids, timestamps or KPI numbers). ``PII_ENGINE=presidio`` uses
Microsoft Presidio instead when ``presidio-analyzer`` / ``presidio-anonymizer`` and a spaCy
model are installed (optional; ADR-018), and falls back to the regex engine otherwise.
"""

from __future__ import annotations

import logging
import os
import re
from collections import Counter
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


def _luhn(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


_NOT_ID = r"(?<![A-Za-z0-9-])"  # never inside SITE-010-N1-C2, alm-root-0001, RB-FIB-001 ...
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b")),
    ("CREDIT_CARD", re.compile(_NOT_ID + r"(?:\d[ -]?){12,18}\d(?![\d-])")),
    ("IMEI", re.compile(_NOT_ID + r"\d{15}(?!\d)")),
    ("IMSI", re.compile(_NOT_ID + r"\d{15}(?!\d)")),
    (
        "IP_ADDRESS",
        re.compile(
            r"(?<![\d.])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?!\.?\d)"
        ),
    ),
    ("IP_ADDRESS", re.compile(r"(?<![\w:])(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}(?![\w:])")),
    (
        "PHONE",
        re.compile(
            _NOT_ID
            + r"(?:\+\d{1,3}[ .-]?)?(?:\(\d{2,4}\)[ .-]?|\d{3}[ .-])\d{3}[ .-]\d{4}(?![\d-])"
        ),
    ),
    ("PHONE", re.compile(_NOT_ID + r"\d{3}[.-]\d{4}(?![\d-])")),
    (
        "PERSON",
        re.compile(
            r"\b(?:(?:[Ee]ngineer|[Cc]ontact|[Tt]echnician|[Cc]ustomer|[Bb]y)\s+)*"
            r"(?:(?:Mr|Ms|Mrs|Dr)\.?\s+|(?<=[Ee]ngineer )|(?<=[Cc]ontact )|(?<=[Tt]echnician ))"
            r"(?!(?:Mr|Ms|Mrs|Dr)\b)((?:[A-Z][a-z]+)(?:\s+[A-Z][a-z]+){0,2})"
        ),
    ),
]


@dataclass
class Redaction:
    text: str
    counts: Counter = field(default_factory=Counter)

    @property
    def total(self) -> int:
        return sum(self.counts.values())


def _regex(text: str) -> Redaction:
    counts: Counter = Counter()
    spans: list[tuple[int, int, str]] = []

    def free(a: int, b: int) -> bool:
        return all(b <= s or a >= e for s, e, _ in spans)

    for kind, pat in PATTERNS:
        for m in pat.finditer(text):
            a, b = m.span(1) if kind == "PERSON" else m.span()
            raw = text[a:b]
            digits = re.sub(r"\D", "", raw)
            if kind == "CREDIT_CARD" and not (13 <= len(digits) <= 19 and _luhn(digits)):
                continue
            if kind == "CREDIT_CARD" and re.fullmatch(r"\d{15}", raw):
                continue  # a bare 15-digit number is an IMEI / IMSI, not a card
            if kind in ("IMEI", "IMSI"):
                hint = text[max(0, a - 16) : a].lower()
                said = "IMEI" if "imei" in hint else "IMSI" if "imsi" in hint else None
                if (said or ("IMEI" if _luhn(raw) else "IMSI")) != kind:
                    continue
            if free(a, b):
                spans.append((a, b, kind))
    out, last = [], 0
    for a, b, kind in sorted(spans):
        counts[kind] += 1
        out.append(text[last:a] + f"<{kind}_{counts[kind]}>")
        last = b
    out.append(text[last:])
    return Redaction("".join(out), counts)


_presidio = None


def _presidio_engine():  # pragma: no cover - optional dependency
    global _presidio
    if _presidio is None:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine

        _presidio = (AnalyzerEngine(), AnonymizerEngine())
    return _presidio


def engine_name() -> str:
    if os.getenv("PII_ENGINE", "regex") == "presidio":
        try:
            _presidio_engine()
            return "presidio"
        except Exception as exc:  # noqa: BLE001 - not installed / no spaCy model
            logger.warning("presidio unavailable (%s); using regex PII engine", type(exc).__name__)
    return "regex"


def redact(text: str) -> Redaction:
    if engine_name() == "presidio":  # pragma: no cover - optional dependency
        analyzer, anonymizer = _presidio_engine()
        results = analyzer.analyze(text=text, language="en")
        counts = Counter(r.entity_type for r in results)
        return Redaction(anonymizer.anonymize(text=text, analyzer_results=results).text, counts)
    return _regex(text)
