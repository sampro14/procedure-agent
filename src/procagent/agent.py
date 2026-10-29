"""A small state-machine agent that follows a written procedure.

Design rules:
  * Legally required wording comes only from the procedure file, verbatim.
  * Offers are only built through PaymentPlan, which enforces the client's limits.
  * Every turn records its state, intent and the exact text sources (a decision trace),
    so a reviewer can answer "why did it say that?" without guessing.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Callable, Optional

from .guardrails import OfferOutOfBounds, PaymentPlan
from .intent import Intent, classify
from .procedure import Procedure


@dataclass
class Turn:
    text: str
    step: str
    state: str
    intent: Optional[str] = None
    disclosures: list[str] = field(default_factory=list)
    offer: Optional[dict] = None

    def to_dict(self) -> dict:
        return asdict(self)


class Agent:
    def __init__(self, procedure: Procedure, llm: Optional[Callable[[str], str]] = None):
        self.p = procedure
        self.llm = llm
        self.state = "await_holder"
        self.pending: Optional[PaymentPlan] = None
        self.trace: list[Turn] = []

    # -- composition -------------------------------------------------------
    def _say(self, step: str, intent: Optional[Intent] = None, **fmt) -> Turn:
        spec = self.p.steps[step]
        ctx = {**self.p.context, **fmt}
        parts, ids = [], []
        if spec.get("say"):
            parts.append(spec["say"].format(**ctx))
        for d in spec.get("disclose", []):
            parts.append(self.p.disclosures[d].text)  # verbatim, never formatted or rephrased
            ids.append(d)
        if spec.get("ask"):
            parts.append(spec["ask"].format(**ctx))
        offer = None
        if self.pending is not None and step in {"negotiate", "counter", "confirm_plan"}:
            offer = {"monthly": self.pending.monthly, "months": self.pending.months}
        turn = Turn(" ".join(parts), step, self.state, intent.label if intent else None, ids, offer)
        self.trace.append(turn)
        return turn

    def _offer(self, requested: Optional[float], intent: Intent) -> Turn:
        lim, bal = self.p.limits, float(self.p.context["balance"])
        try:
            plan = PaymentPlan.closest_to(requested, lim, bal)
        except OfferOutOfBounds:  # defensive: fall back to the client's own minimum plan
            plan = PaymentPlan.closest_to(None, lim, bal)
        self.pending = plan
        self.state = "offered"
        step = "negotiate" if requested is not None and plan.monthly == round(requested, 2) else "counter"
        if requested is None:
            step = "negotiate"
        return self._say(step, intent, amount=f"{plan.monthly:.2f}", months=plan.months)

    # -- public API ----------------------------------------------------------
    def start(self) -> Turn:
        return self._say("greet")

    def respond(self, caller_text: str) -> Turn:
        intent = classify(caller_text, self.llm)

        if self.state == "done":
            return self._say("close", intent)
        # Universal rules apply in every state.
        if intent.label == "cease_contact":
            self.state = "done"
            return self._say("cease", intent)

        if self.state == "await_holder":
            if intent.label == "wrong_person":
                self.state = "done"
                return self._say("wrong_person", intent)
            if intent.label in {"confirm_identity", "accept"}:
                self.state = "await_digits"
                return self._say("verify_identity", intent)
            return self._reask("await_holder", "greet", intent)

        if self.state == "await_digits":
            if intent.label == "account_digits":  # demo stub: any four digits verify
                self.state = "negotiating"
                return self._say("state_debt", intent)
            return self._reask("await_digits", "verify_identity", intent)

        if intent.label == "dispute":
            self.state = "done"
            return self._say("dispute", intent)

        if self.state in {"negotiating", "offered"}:
            if intent.label == "request_plan":
                return self._offer(intent.amount, intent)
            if intent.label in {"accept", "confirm_identity"}:  # a bare "yes" means yes here
                if self.state == "offered":
                    self.state = "done"
                    return self._say("confirm_plan", intent, amount=f"{self.pending.monthly:.2f}", months=self.pending.months)
                return self._offer(None, intent)
            if intent.label == "refuse":
                self.state = "done"
                return self._say("close", intent)
        return self._reask(self.state, "state_debt" if self.state == "negotiating" else "negotiate", intent, mini=True)

    def _reask(self, state: str, step: str, intent: Intent, mini: bool = False) -> Turn:
        """Repeat the question without re-delivering disclosures."""
        spec = self.p.steps[step]
        ctx = {**self.p.context}
        if self.pending:
            ctx.update(amount=f"{self.pending.monthly:.2f}", months=self.pending.months)
        text = (spec.get("ask") or spec.get("say", "")).format(**ctx)
        turn = Turn(f"Sorry, I did not catch that. {text}", step, state, intent.label)
        self.trace.append(turn)
        return turn
