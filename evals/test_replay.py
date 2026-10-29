"""The release gate: replay every recorded caller script through the current agent
and require every metric to pass. CI runs this before anything ships."""
import os

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")

import pytest
from deepeval import assert_test

from evals.metrics import ALL_METRICS, to_test_case
from evals.replay import load_scenarios, replay

SCENARIOS = load_scenarios()


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_replay_follows_procedure(scenario):
    case = to_test_case(scenario, replay(scenario))
    assert_test(case, [m() for m in ALL_METRICS], run_async=False)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_replay_reaches_expected_outcome(scenario):
    """Disclosure checks alone would pass a bot that never finishes the call."""
    last = replay(scenario)[-1]
    assert last["step"] == scenario["expected_final_step"], last["text"]
