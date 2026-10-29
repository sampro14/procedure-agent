"""Load and validate the written procedure."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Disclosure:
    id: str
    text: str


@dataclass(frozen=True)
class Limits:
    min_monthly_payment: float
    max_months: int
    min_down_payment: float = 0.0


@dataclass(frozen=True)
class Procedure:
    id: str
    version: str
    context: dict
    disclosures: dict[str, Disclosure]
    limits: Limits
    steps: dict[str, dict]


def load_procedure(path: str | Path) -> Procedure:
    raw = yaml.safe_load(Path(path).read_text())
    disclosures = {k: Disclosure(id=k, **v) for k, v in raw["disclosures"].items()}
    steps = raw["steps"]
    for name, step in steps.items():
        for d in step.get("disclose", []):
            if d not in disclosures:
                raise ValueError(f"step {name!r} references unknown disclosure {d!r}")
    context = {
        "agent_name": raw["agent_name"],
        "company": raw["company"],
        "creditor": raw["debt"]["creditor"],
        "balance": f"{raw['debt']['balance']:.2f}",
    }
    return Procedure(
        id=raw["id"],
        version=str(raw["version"]),
        context=context,
        disclosures=disclosures,
        limits=Limits(**raw["negotiation"]),
        steps=steps,
    )
