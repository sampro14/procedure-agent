"""Intent layer: every reply is grounded in what the caller actually said.

Rules first (deterministic, auditable). An optional LLM callable is consulted only
when the rules return UNKNOWN, and its answer must be one of the allowed labels.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional

INTENTS = {
    "confirm_identity", "wrong_person", "dispute", "cease_contact", "account_digits",
    "request_plan", "accept", "refuse", "unknown",
}


@dataclass(frozen=True)
class Intent:
    label: str
    amount: Optional[float] = None
    source: str = "rules"


_MONEY = re.compile(r"\$\s?(\d[\d,]*(?:\.\d{1,2})?)|(\d[\d,]*(?:\.\d{1,2})?)\s?(?:dollars|bucks)")


def extract_amount(text: str) -> Optional[float]:
    m = _MONEY.search(text)
    if not m:
        return None
    return float((m.group(1) or m.group(2)).replace(",", ""))


def classify(text: str, llm: Optional[Callable[[str], str]] = None) -> Intent:
    t = text.lower().strip()
    amount = extract_amount(t)
    if re.search(r"stop (calling|contacting)|cease|do not contact|don't contact|never call", t):
        return Intent("cease_contact")
    if re.search(r"\bdispute|not my debt|don't owe|do not owe|not mine\b", t):
        return Intent("dispute")
    if re.search(r"wrong (number|person)|not (him|her|them)|isn't here|doesn't live", t):
        return Intent("wrong_person")
    if re.fullmatch(r"\W*\d{4}\W*", t):
        return Intent("account_digits")
    if re.search(r"\b(payment plan|monthly|per month|a month|/month|installments?)\b", t) or (amount and "?" not in t and not re.search(r"\b(yes|ok|okay|sure)\b", t)):
        return Intent("request_plan", amount=amount)
    if re.search(r"\b(no|can't|cannot|won't|refuse|not paying)\b", t):
        return Intent("refuse")
    if re.search(r"\b(yes|yeah|yep|speaking|that's me|this is he|this is she|i am)\b", t) and not re.search(r"\b(ok|okay|works|deal|agree)\b", t):
        return Intent("confirm_identity")
    if re.search(r"\b(ok|okay|works|deal|agree|sounds good|sure|fine|let's do it)\b", t):
        return Intent("accept")
    if llm is not None:
        label = llm(text).strip().lower()
        if label in INTENTS and label != "unknown":
            return Intent(label, amount=amount, source="llm")
    return Intent("unknown", amount=amount)
