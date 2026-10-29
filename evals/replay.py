"""Replay a recorded caller script through the CURRENT agent and return a transcript."""
from __future__ import annotations

import json
from pathlib import Path

from procagent import Agent, load_procedure

ROOT = Path(__file__).resolve().parent.parent
PROCEDURE = ROOT / "procedures" / "collections_v1.yaml"
CONVERSATIONS = ROOT / "conversations"


def load_scenarios() -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(CONVERSATIONS.glob("*.json"))]


def replay(scenario: dict, procedure_path: Path = PROCEDURE) -> list[dict]:
    """Returns [{'role': 'agent'|'caller', 'text': ..., ...trace}] for the whole call."""
    agent = Agent(load_procedure(procedure_path))
    transcript = [{"role": "agent", **agent.start().to_dict()}]
    for line in scenario["caller"]:
        transcript.append({"role": "caller", "text": line})
        transcript.append({"role": "agent", **agent.respond(line).to_dict()})
    return transcript


if __name__ == "__main__":
    import sys

    sc = json.loads(Path(sys.argv[1]).read_text())
    for t in replay(sc):
        print(f"{t['role']:>6}: {t['text']}")
