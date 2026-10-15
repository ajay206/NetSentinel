#!/usr/bin/env python3
"""CI guard (Step 18): no service may call a model backend directly; only services/llm-gateway.

Fails if any file under services/ or apps/ (outside services/llm-gateway) mentions the Ollama
port, its chat/generate API, or OLLAMA_URL. Docs, tests and compose wiring for the gateway are
outside the scanned tree or explicitly allowed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN = ["services", "apps", "libs"]
ALLOWED = ("services/llm-gateway/",)
SKIP_DIRS = {"node_modules", "dist", ".venv", "__pycache__", "build"}
SUFFIXES = {".py", ".ts", ".tsx", ".js", ".toml", ".yaml", ".yml", ".json", ".env", ""}
PATTERN = re.compile(
    r"11434|/api/(chat|generate)\b|OLLAMA_URL|OllamaLLM|api\.openai\.com|generativelanguage\.googleapis"
)


def violations(root: Path = ROOT) -> list[str]:
    out: list[str] = []
    for top in SCAN:
        for path in (root / top).rglob("*"):
            rel = path.relative_to(root).as_posix()
            if not path.is_file() or path.suffix not in SUFFIXES or rel.startswith(ALLOWED):
                continue
            if SKIP_DIRS & set(path.parts) or path.name.endswith(".md"):
                continue
            for n, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
                if PATTERN.search(line):
                    out.append(f"{rel}:{n}: {line.strip()[:120]}")
    return out


def main() -> int:
    bad = violations()
    for v in bad:
        print(f"direct LLM call outside llm-gateway: {v}")
    if not bad:
        print("ok: only services/llm-gateway talks to model backends")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
