"""Docs check: render every mermaid block and verify relative markdown links/images.

Usage: python3 scripts/check_docs.py [repo_root]   (needs Node for npx mermaid-cli)
Exit code 1 if any diagram fails to parse or any relative link/image target is missing.
"""

import json
import pathlib
import re
import subprocess
import sys
import tempfile
import urllib.parse

SKIP = {"node_modules", ".venv", ".git", "dist", ".pytest_cache", ".ruff_cache"}
MERMAID = re.compile(r"```mermaid\n(.*?)```", re.S)
LINK = re.compile(r'!?\[[^\]]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)')


def main() -> int:
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    tmp = pathlib.Path(tempfile.mkdtemp())
    puppeteer_cfg = tmp / "puppeteer.json"
    puppeteer_cfg.write_text(json.dumps({"args": ["--no-sandbox"]}))
    docs = [p for p in root.rglob("*.md") if not SKIP & set(p.parts)]
    problems = 0
    for doc in docs:
        text = doc.read_text()
        rel = doc.relative_to(root)
        for i, block in enumerate(MERMAID.finditer(text)):
            src = tmp / f"{doc.stem}-{i}.mmd"
            src.write_text(block.group(1))
            cmd = ["npx", "-y", "@mermaid-js/mermaid-cli", "-p", str(puppeteer_cfg)]
            cmd += ["-i", str(src), "-o", f"{src}.svg"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"OK   mermaid {rel}#{i}")
            else:
                problems += 1
                print(f"FAIL mermaid {rel}#{i}\n{result.stderr[-600:]}")
        # Ignore links inside code blocks and inline code
        body = re.sub(r"```.*?```", "", text, flags=re.S)
        body = re.sub(r"`[^`\n]*`", "", body)
        for match in LINK.finditer(body):
            url = match.group(1)
            if re.match(r"^(https?:|mailto:|#)", url):
                continue
            target = (doc.parent / urllib.parse.unquote(url.split("#")[0])).resolve()
            if not target.exists():
                problems += 1
                print(f"FAIL link {rel} -> {url}")
    print(f"markdown files: {len(docs)}, problems: {problems}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
