import pytest
from procagent import OfferOutOfBounds, PaymentPlan, load_procedure
from evals.replay import PROCEDURE

LIM = load_procedure(PROCEDURE).limits


def test_constructor_rejects_low_payment():
    with pytest.raises(OfferOutOfBounds):
        PaymentPlan(40, 12, LIM, 1200)


def test_constructor_rejects_long_term():
    with pytest.raises(OfferOutOfBounds):
        PaymentPlan(100, 24, LIM, 1200)


def test_constructor_rejects_plan_that_does_not_cover_balance():
    with pytest.raises(OfferOutOfBounds):
        PaymentPlan(100, 6, LIM, 1200)


@pytest.mark.parametrize("ask", [None, 1, 40, 99.99, 100, 150, 400, 5000, 1e9])
def test_closest_to_is_always_within_limits(ask):
    plan = PaymentPlan.closest_to(ask, LIM, 1200)
    assert plan.monthly >= LIM.min_monthly_payment and plan.months <= LIM.max_months
    assert plan.monthly * plan.months >= 1200 - 0.005


def test_uneven_balance_raises_payment_to_fit_term():
    plan = PaymentPlan.closest_to(100, LIM, 1234.56)
    assert plan.months == 12 and plan.monthly * 12 >= 1234.56
