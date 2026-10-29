import pytest
from procagent import Agent, load_procedure
from procagent.intent import classify
from evals.replay import PROCEDURE


@pytest.mark.parametrize("text,label,amount", [
    ("stop calling me", "cease_contact", None),
    ("I dispute this", "dispute", None),
    ("wrong number", "wrong_person", None),
    ("4821", "account_digits", None),
    ("can I pay $75 a month", "request_plan", 75.0),
    ("no, I am not paying", "refuse", None),
    ("yes speaking", "confirm_identity", None),
    ("sounds good", "accept", None),
    ("purple elephant", "unknown", None),
])
def test_rules(text, label, amount):
    i = classify(text)
    assert (i.label, i.amount) == (label, amount)


def test_llm_fallback_only_used_for_unknown_and_must_return_valid_label():
    assert classify("purple elephant", llm=lambda t: "dispute").label == "dispute"
    assert classify("purple elephant", llm=lambda t: "make_a_free_offer").label == "unknown"
    assert classify("stop calling me", llm=lambda t: "accept").label == "cease_contact"  # rules win


def test_balance_never_revealed_before_verification():
    a = Agent(load_procedure(PROCEDURE))
    texts = [a.start().text, a.respond("what is this about").text, a.respond("how much do I owe").text]
    assert not any("$" in t for t in texts)


def test_reask_does_not_repeat_disclosures():
    a = Agent(load_procedure(PROCEDURE))
    a.start()
    t = a.respond("mumble")
    assert t.disclosures == []


def test_cease_contact_in_any_state_ends_call():
    a = Agent(load_procedure(PROCEDURE))
    a.start(); a.respond("yes"); a.respond("1234"); a.respond("$100 a month")
    t = a.respond("stop contacting me")
    assert "cease_ack" in t.disclosures and a.state == "done"
