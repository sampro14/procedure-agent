"""Tests of the tests. A gate that cannot fail is worthless, so we break a known-good
transcript in realistic ways and require the right metric to catch each one."""
import copy
import os

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")

import pytest

from evals.metrics import APPROVED, DisclosureOrderMetric, OfferWithinLimitsMetric, VerbatimDisclosureMetric, to_test_case
from evals.replay import PROCEDURE, load_scenarios, replay

SC = {s["id"]: s for s in load_scenarios()}
MIRANDA = APPROVED["disclosures"]["mini_miranda"]["text"]
RECORDING = APPROVED["disclosures"]["recording"]["text"]


def run(metric, scenario_id, mutate):
    sc = SC[scenario_id]
    tr = copy.deepcopy(replay(sc))
    mutate(tr)
    m = metric()
    m.measure(to_test_case(sc, tr))
    return m


def agent_text(tr, needle):
    return next(t for t in tr if t["role"] == "agent" and needle in t["text"])


def test_baseline_passes():
    for metric in (VerbatimDisclosureMetric, DisclosureOrderMetric, OfferWithinLimitsMetric):
        assert run(metric, "happy_path_plan", lambda tr: None).success


def test_paraphrased_disclosure_fails():
    def mutate(tr):
        t = agent_text(tr, MIRANDA)
        t["text"] = t["text"].replace(MIRANDA, "This is a debt collector trying to collect a debt.")
    m = run(VerbatimDisclosureMetric, "happy_path_plan", mutate)
    assert not m.success and "mini_miranda" in m.reason


def test_single_dropped_word_fails():
    def mutate(tr):
        t = agent_text(tr, MIRANDA)
        t["text"] = t["text"].replace("an attempt to collect a debt", "attempt to collect a debt")
    m = run(VerbatimDisclosureMetric, "happy_path_plan", mutate)
    assert not m.success and "an" in m.reason


def test_changed_case_or_punctuation_fails():
    def mutate(tr):
        t = agent_text(tr, MIRANDA)
        t["text"] = t["text"].replace("debt collector.", "Debt Collector,")
    assert not run(VerbatimDisclosureMetric, "happy_path_plan", mutate).success


def test_missing_recording_notice_fails():
    def mutate(tr):
        tr[0]["text"] = tr[0]["text"].replace(RECORDING, "")
    assert not run(VerbatimDisclosureMetric, "happy_path_plan", mutate).success


def test_disclosure_after_balance_fails_order():
    def mutate(tr):
        t = agent_text(tr, MIRANDA)
        head, tail = t["text"].split(MIRANDA)
        t["text"] = tail.strip() + " " + MIRANDA  # balance first, disclosure after
    m = run(DisclosureOrderMetric, "happy_path_plan", mutate)
    assert not m.success and "mini_miranda" in m.reason


def test_missing_validation_notice_on_dispute_fails():
    sc = SC["dispute"]
    assert run(VerbatimDisclosureMetric, "dispute", lambda tr: None).success
    def mutate(tr):
        t = agent_text(tr, "I have noted your dispute")
        t["text"] = "I have noted your dispute."
    assert not run(VerbatimDisclosureMetric, "dispute", mutate).success


@pytest.mark.parametrize("bad", ["$40.00 per month, for 12 months", "$100.00 per month, for 18 months"])
def test_out_of_bounds_offer_fails(bad):
    def mutate(tr):
        t = agent_text(tr, "per month")
        t["text"] = f"I can set up a plan of {bad}. Would that work for you?"
    assert not run(OfferWithinLimitsMetric, "happy_path_plan", mutate).success


def test_editing_the_procedure_cannot_move_the_goalposts(tmp_path):
    """Someone 'cleans up' the wording in the procedure. The gate compares against the
    separately approved copy, so the release is blocked."""
    edited = PROCEDURE.read_text().replace("This is an attempt to collect a debt, and any", "We are trying to collect a debt, and any")
    assert edited != PROCEDURE.read_text()
    p = tmp_path / "edited.yaml"
    p.write_text(edited)
    sc = SC["happy_path_plan"]
    m = VerbatimDisclosureMetric()
    m.measure(to_test_case(sc, replay(sc, procedure_path=p)))
    assert not m.success
