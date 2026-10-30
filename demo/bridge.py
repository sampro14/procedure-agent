"""Browser bridge for the live demo: runs the real Agent and returns JSON to the page.

This is a transport, like a WebSocket server would be: it holds one Agent and
serialises each Turn. No conversation logic lives here.
"""
from __future__ import annotations

import json
from pathlib import Path

from procagent import Agent, load_procedure

ROOT = Path(__file__).resolve().parent
_procedure = load_procedure(ROOT / "procedures" / "collections_v1.yaml")
_approved = json.loads((ROOT / "compliance" / "approved_disclosures.json").read_text())["disclosures"]
_agent: Agent | None = None


def _payload(turn) -> str:
    """Turn plus the exact disclosure texts it carried and whether they match the approved copy."""
    d = turn.to_dict()
    d["done"] = _agent.state == "done"
    d["disclosure_checks"] = [
        {"id": i, "text": _procedure.disclosures[i].text, "verbatim": _approved[i]["text"] in turn.text}
        for i in turn.disclosures
    ]
    return json.dumps(d)


def start() -> str:
    global _agent
    _agent = Agent(_procedure)
    return _payload(_agent.start())


def respond(text: str) -> str:
    return _payload(_agent.respond(text))


def info() -> str:
    lim = _procedure.limits
    return json.dumps({
        "procedure": f"{_procedure.id} v{_procedure.version}",
        "balance": _procedure.context["balance"],
        "min_monthly": lim.min_monthly_payment,
        "max_months": lim.max_months,
    })
