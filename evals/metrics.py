"""DeepEval metrics for a regulated procedure.

All three are deterministic: no LLM judge. A wrong word in a disclosure is a compliance
incident, so the check is exact string containment against the approved wording, with a
fuzzy diff only to explain a failure.
"""
from __future__ import annotations

import difflib
import json
import re
from pathlib import Path

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

APPROVED = json.loads((Path(__file__).resolve().parent.parent / "compliance" / "approved_disclosures.json").read_text())


def agent_turns(case: LLMTestCase) -> list[str]:
    return [t["text"] for t in case.metadata["transcript"] if t["role"] == "agent"]


def required_ids(case: LLMTestCase) -> list[str]:
    """Always-required disclosures, plus any the scenario declares are triggered."""
    always = [k for k, v in APPROVED["disclosures"].items() if v["always"]]
    return always + [d for d in case.metadata.get("expected_disclosures", []) if d not in always]


class _Base(BaseMetric):
    threshold = 1.0
    async_mode = False
    include_reason = True
    strict_mode = True
    evaluation_model = None

    def __init__(self):
        self.score = 0.0
        self.success = False
        self.reason = ""

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success

    def _finish(self, problems: list[str]) -> float:
        self.score = 0.0 if problems else 1.0
        self.success = not problems
        self.reason = "ok" if not problems else "; ".join(problems)
        return self.score


class VerbatimDisclosureMetric(_Base):
    """Every required disclosure appears, word for word, inside a single agent turn."""

    @property
    def __name__(self) -> str:
        return "Verbatim Disclosure"

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        turns, problems = agent_turns(test_case), []
        for did in required_ids(test_case):
            approved = APPROVED["disclosures"][did]["text"]
            if any(approved in t for t in turns):
                continue
            best = max((difflib.SequenceMatcher(None, approved, t).find_longest_match(0, len(approved), 0, len(t)).size for t in turns), default=0)
            sentence = next((t for t in turns if best and difflib.SequenceMatcher(None, approved, t).find_longest_match(0, len(approved), 0, len(t)).size == best), "")
            diff = [w for w in difflib.ndiff(approved.split(), sentence.split()) if w[0] in "-"][:6]
            problems.append(f"{did}: not delivered verbatim (missing words: {[w[2:] for w in diff]})" if sentence else f"{did}: never delivered")
        return self._finish(problems)


class DisclosureOrderMetric(_Base):
    """A disclosure must be delivered no later than the turn that makes it necessary."""

    @property
    def __name__(self) -> str:
        return "Disclosure Order"

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        turns, problems = agent_turns(test_case), []
        for did, spec in APPROVED["disclosures"].items():
            for marker in spec.get("must_precede", []):
                trigger = next((i for i, t in enumerate(turns) if marker in t), None)
                if trigger is None:
                    continue  # the conversation never reached that point
                delivered = next((i for i, t in enumerate(turns) if spec["text"] in t), None)
                # Same turn is fine only if the disclosure comes first within it.
                same_turn_late = delivered == trigger and turns[trigger].index(spec["text"]) > turns[trigger].index(marker)
                if delivered is None or delivered > trigger or same_turn_late:
                    problems.append(f"{did}: must come before {marker!r} (turn {trigger}) but was {'missing' if delivered is None else f'at turn {delivered}'}")
        return self._finish(problems)


class OfferWithinLimitsMetric(_Base):
    """No payment plan the agent states may break the client's limits."""

    @property
    def __name__(self) -> str:
        return "Offer Within Limits"

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        lim, problems = APPROVED["limits"], []
        for i, t in enumerate(agent_turns(test_case)):
            for m in re.finditer(r"\$(\d[\d,]*(?:\.\d\d)?) per month", t):
                if float(m.group(1).replace(",", "")) < lim["min_monthly_payment"] - 1e-9:
                    problems.append(f"turn {i}: ${m.group(1)}/month is below the minimum {lim['min_monthly_payment']:.2f}")
            for m in re.finditer(r"for (\d+) months", t):
                if int(m.group(1)) > lim["max_months"]:
                    problems.append(f"turn {i}: {m.group(1)} months exceeds the maximum {lim['max_months']}")
        return self._finish(problems)


ALL_METRICS = [VerbatimDisclosureMetric, DisclosureOrderMetric, OfferWithinLimitsMetric]


def to_test_case(scenario: dict, transcript: list[dict]) -> LLMTestCase:
    return LLMTestCase(
        input="\n".join(t["text"] for t in transcript if t["role"] == "caller"),
        actual_output="\n".join(t["text"] for t in transcript if t["role"] == "agent"),
        metadata={"transcript": transcript, "expected_disclosures": scenario.get("expected_disclosures", []), "scenario": scenario["id"]},
    )
