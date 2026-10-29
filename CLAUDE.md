# CLAUDE.md

Guidance for Claude Code (or any coding agent) working in this repo. Read this first, then README.md.

## What this project is
A chat agent that follows a written procedure (`procedures/*.yaml`) for a fictional debt-collection call, plus a DeepEval replay gate (`evals/`) that checks required disclosures word for word. It is a portfolio project for an Agent Engineer role in regulated conversational AI. Quality bar: readable, small, honest about limits.

## Commands
```bash
pip install -e .
export DEEPEVAL_TELEMETRY_OPT_OUT=YES
pytest tests          # unit tests
pytest evals          # release gate (replays conversations/*.json)
pytest                # everything; must stay green
python -m procagent.cli
python -m evals.replay conversations/<name>.json
```

## Invariants (do not break these)
1. **Disclosure text is never generated or formatted.** It is copied verbatim from the procedure into replies (`Agent._say`). Never pass it through `.format()`, an LLM, or any rewording.
2. **The gate checks against `compliance/approved_disclosures.json`, not the procedure YAML.** When a user asks to change disclosure wording, change BOTH files deliberately and say so. Never make the metrics read wording from the procedure.
3. **Offers only come from `PaymentPlan`.** Do not build offer text from raw numbers. New limits go in the procedure's `negotiation` block, in `PaymentPlan.__post_init__`, and in `OfferWithinLimitsMetric` + approved JSON.
4. **Metrics are deterministic** (exact string checks, no LLM judge) for compliance boundaries. An LLM may be used for intent fallback only, and only returns a label from `INTENTS`; rules win for cease/dispute/wrong_person.
5. **Every behaviour change needs a replay scenario** in `conversations/` (with `expected_final_step` and `expected_disclosures`) and, for new rules, a mutation test in `evals/test_gate_catches_regressions.py` proving the gate fails when broken.
6. Keep the balance and any debt detail out of replies until identity is verified.

## Layout
- `procedures/collections_v1.yaml`: steps (`say` / `disclose` / `ask`), disclosures, limits
- `src/procagent/`: `procedure.py` (loader), `intent.py` (classifier), `agent.py` (state machine), `guardrails.py`, `cli.py`
- `compliance/approved_disclosures.json`: approved wording, `always` flag, `must_precede` markers, limits
- `evals/`: `metrics.py` (3 DeepEval BaseMetric subclasses), `replay.py`, `test_replay.py` (the gate), `test_gate_catches_regressions.py`
- `conversations/*.json`: `{id, caller[], expected_disclosures[], expected_final_step}`

## How to do common tasks
- **Add a disclosure:** add text to the procedure + approved JSON (with `always`/`must_precede`), reference it in a step's `disclose`, add a scenario that triggers it, add a mutation test.
- **Add a step/intent:** add the step to the YAML, the regex to `intent.py` (order matters: more specific first), the transition in `Agent.respond`, a scenario, and a unit test.
- **Add a new procedure (another client):** copy the YAML, new approved JSON, parametrise `PROCEDURE` in `evals/replay.py`.
- **Wire a real LLM for intent:** pass a callable `str -> str` as `Agent(llm=...)`; keep the label whitelist.
- **Wire a transport (FastAPI WebSocket):** create `src/procagent/server.py` that holds one `Agent` per connection and returns `Turn.to_dict()`; do not put logic in the transport.

## Style
Python 3.10+, type hints, small functions, docstrings explain *why*. No new dependencies without a reason. Keep the README "Known limits" section truthful when behaviour changes.

## Before you finish any change
Run `pytest`, and state which scenarios and mutation tests cover the change. If you could not verify something, say so.
