"""The live demo is built from the real sources; check the built bundle actually runs a call."""
import importlib.util
import json
import sys

from demo.build import build


def _load_bridge(site):
    sys.path.insert(0, str(site / "py"))
    try:
        spec = importlib.util.spec_from_file_location("demo_bridge", site / "py" / "bridge.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.remove(str(site / "py"))


def test_built_demo_runs_a_call_and_flags_verbatim_disclosures(tmp_path):
    build(tmp_path / "site")
    manifest = json.loads((tmp_path / "site" / "manifest.json").read_text())
    assert "py/procagent/agent.py" in manifest["files"]
    assert {s["id"] for s in manifest["scenarios"]} >= {"happy_path_plan", "dispute"}

    bridge = _load_bridge(tmp_path / "site")
    greet = json.loads(bridge.start())
    assert greet["disclosure_checks"] == [{"id": "recording", "text": greet["disclosure_checks"][0]["text"], "verbatim": True}]

    turns = [json.loads(bridge.respond(line)) for line in ["yes speaking", "4821", "can we do $40 a month?", "ok"]]
    assert turns[1]["disclosure_checks"][0]["id"] == "mini_miranda"
    assert turns[2]["offer"] == {"monthly": 100.0, "months": 12}
    assert turns[-1]["step"] == "confirm_plan" and turns[-1]["done"]
