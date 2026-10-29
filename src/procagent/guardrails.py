"""Out-of-bounds offers are made impossible, not just unlikely.

The agent can only produce an offer by constructing a PaymentPlan. The constructor
raises if the plan violates the client's limits, so no code path (and no LLM output)
can put a bad number into a reply.
"""
from __future__ import annotations

from dataclasses import dataclass

from .procedure import Limits


class OfferOutOfBounds(ValueError):
    pass


@dataclass(frozen=True)
class PaymentPlan:
    monthly: float
    months: int
    limits: Limits
    balance: float

    def __post_init__(self):
        if self.monthly < self.limits.min_monthly_payment:
            raise OfferOutOfBounds(f"monthly {self.monthly} < minimum {self.limits.min_monthly_payment}")
        if self.months > self.limits.max_months or self.months < 1:
            raise OfferOutOfBounds(f"{self.months} months outside 1..{self.limits.max_months}")
        if self.monthly * self.months < self.balance - 0.005:
            raise OfferOutOfBounds("plan would not cover the balance")

    @classmethod
    def closest_to(cls, requested_monthly: float | None, limits: Limits, balance: float) -> "PaymentPlan":
        """Build the most caller-friendly plan that is still within limits."""
        monthly = max(requested_monthly or 0, limits.min_monthly_payment)
        # Fewest months >= what the balance needs at this payment, capped by max_months.
        months = -(-balance // monthly)  # ceil
        if months > limits.max_months:
            monthly = -(-balance * 100 // limits.max_months) / 100  # raise payment to fit the term
            months = limits.max_months
        return cls(monthly=round(float(monthly), 2), months=int(months), limits=limits, balance=balance)
