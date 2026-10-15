import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "check_llm_calls", ROOT / "scripts/check_llm_calls.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_repo_has_no_direct_llm_calls():
    assert mod.violations() == []


def test_detects_direct_ollama_call(tmp_path):
    (tmp_path / "services/x").mkdir(parents=True)
    (tmp_path / "services/x/a.py").write_text('URL = "http://localhost:11434/api/chat"\n')
    (tmp_path / "services/llm-gateway").mkdir(parents=True)
    (tmp_path / "services/llm-gateway/ok.py").write_text('URL = "http://localhost:11434"\n')
    for d in ("apps", "libs"):
        (tmp_path / d).mkdir()
    assert [v.split(":")[0] for v in mod.violations(tmp_path)] == ["services/x/a.py"]
