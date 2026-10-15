"""The questionnaire has to be correct whether a human or a script answers it."""

from __future__ import annotations

import pytest
import yaml

from titlei.config import ModelConfig
from titlei.wizard import (
    QUESTIONS,
    WizardAborted,
    answers_to_config,
    collect_answers,
    run_wizard,
    save_config,
    summarise,
)


def _scripted(responses):
    """An input function that replays a list of answers."""
    queue = list(responses)

    def read(_prompt: str) -> str:
        return queue.pop(0)

    return read


def test_pressing_enter_throughout_reproduces_the_published_scenario():
    config, label = run_wizard(
        input_fn=_scripted([""] * len(QUESTIONS)), output_fn=lambda _: None
    )
    assert config == ModelConfig()
    assert label == ""


def test_answers_can_be_supplied_instead_of_asked():
    def refuse(_prompt: str) -> str:
        raise AssertionError("should not prompt for a pre-supplied answer")

    answers = {q.key: q.default for q in QUESTIONS}
    answers["budget_millions"] = 750.0
    config, _ = run_wizard(
        input_fn=refuse, output_fn=lambda _: None, answers=answers
    )
    assert config.extra_budget == 750e6


def test_academic_weight_is_the_complement_of_financial():
    config = answers_to_config(
        {**{q.key: q.default for q in QUESTIONS}, "financial_weight": 0.4}
    )
    assert config.financial_weight == 0.4
    assert config.academic_weight == pytest.approx(0.6)


def test_invalid_answers_are_rejected_and_re_asked():
    messages = []
    responses = [""] * len(QUESTIONS)
    budget_index = [q.key for q in QUESTIONS].index("budget_millions")
    responses[budget_index : budget_index + 1] = ["-5", "not a number", "300"]

    config, _ = run_wizard(
        input_fn=_scripted(responses), output_fn=messages.append
    )
    assert config.extra_budget == 300e6
    assert any("greater than zero" in m for m in messages)
    assert any("could not read" in m for m in messages)


def test_out_of_range_weight_is_rejected():
    responses = [""] * len(QUESTIONS)
    index = [q.key for q in QUESTIONS].index("financial_weight")
    responses[index : index + 1] = ["1.5", "0.5"]
    config, _ = run_wizard(input_fn=_scripted(responses), output_fn=lambda _: None)
    assert config.financial_weight == 0.5


def test_pre_supplied_answers_are_validated_too():
    answers = {q.key: q.default for q in QUESTIONS}
    answers["financial_weight"] = 2.0
    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        collect_answers(answers=answers, output_fn=lambda _: None)


def test_sweep_budgets_parse_from_a_space_separated_list():
    responses = [""] * len(QUESTIONS)
    index = [q.key for q in QUESTIONS].index("sweep_budgets")
    responses[index] = "100 300 600"
    config, _ = run_wizard(input_fn=_scripted(responses), output_fn=lambda _: None)
    assert config.sweep_budgets == (100e6, 300e6, 600e6)


def test_displayed_defaults_are_valid_input():
    """Whatever a prompt shows as its default must parse if retyped."""
    from titlei.wizard import _format_default

    for question in QUESTIONS:
        shown = _format_default(question)
        if not shown or shown == "auto":
            continue
        reparsed = question.cast(shown)
        assert question.check(reparsed) is None, question.key
        if question.key == "sweep_budgets":
            assert reparsed == question.default


def test_quitting_aborts():
    with pytest.raises(WizardAborted):
        run_wizard(input_fn=_scripted(["q"]), output_fn=lambda _: None)


@pytest.mark.parametrize("interruption", [EOFError, KeyboardInterrupt],
                         ids=["ctrl-d or input ran out", "ctrl-c"])
def test_interrupting_a_question_aborts_cleanly(interruption):
    """Regression: these escaped as a traceback instead of the abort message."""
    def interrupted(_prompt):
        raise interruption

    with pytest.raises(WizardAborted):
        run_wizard(input_fn=interrupted, output_fn=lambda _: None)


def test_every_question_explains_itself():
    for question in QUESTIONS:
        if question.key == "label":
            continue
        assert question.why, f"{question.key} has no explanation"


def test_saved_config_reloads_identically(tmp_path):
    from titlei.config import load_config

    config = ModelConfig().replace(extra_budget=333e6, high_need_cap_per_pupil=4200.0)
    path = save_config(config, tmp_path / "scenario.yaml")

    assert load_config(path) == config
    assert yaml.safe_load(path.read_text())["extra_budget"] == 333e6


def test_summary_names_every_parameter_a_reader_needs():
    text = summarise(ModelConfig(), "My scenario")
    for fragment in ("My scenario", "$500M", "30% financial", "5,000", "60%"):
        assert fragment in text
