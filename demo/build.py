"""Assemble the static demo site from the real sources: python demo/build.py [out_dir]

The page loads the same procagent package, procedure and scenarios the tests use,
so the demo cannot drift from the code that passed the gate.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build(out: Path) -> None:
    shutil.rmtree(out, ignore_errors=True)
    files: list[str] = []

    def copy(src: Path, rel: str) -> None:
        dest = out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        files.append(rel)

    out.mkdir(parents=True)
    shutil.copy2(ROOT / "demo" / "index.html", out / "index.html")
    copy(ROOT / "demo" / "bridge.py", "py/bridge.py")
    for src in sorted((ROOT / "src" / "procagent").glob("*.py")):
        copy(src, f"py/procagent/{src.name}")
    copy(ROOT / "procedures" / "collections_v1.yaml", "py/procedures/collections_v1.yaml")
    copy(ROOT / "compliance" / "approved_disclosures.json", "py/compliance/approved_disclosures.json")

    scenarios = [json.loads(p.read_text()) for p in sorted((ROOT / "conversations").glob("*.json"))]
    (out / "manifest.json").write_text(json.dumps({"files": files, "scenarios": scenarios}, indent=1))


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "_site")
    build(target)
    print(f"built {target}")
