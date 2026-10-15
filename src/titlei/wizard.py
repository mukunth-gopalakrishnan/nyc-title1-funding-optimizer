"""An interactive questionnaire for building a scenario.

Editing YAML is fine if you already know what the knobs do. This asks instead,
one question at a time, each with the reason it matters and what moving it will
do — so someone who has never read the model can still set up a defensible run.

Every question is a :class:`Question`, and answers can also be supplied as a
dict, which is what makes the whole thing testable and scriptable::

    config, label = run_wizard(answers={"budget_millions": 750})
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

from titlei.config import ModelConfig

Caster = Callable[[str], Any]
Validator = Callable[[Any], Optional[str]]


class WizardAborted(RuntimeError):
    """Raised when the user backs out of the questionnaire."""


@dataclass
class Question:
    """One prompt: what is asked, how it is parsed, and what makes it valid."""

    key: str
    prompt: str
    default: Any
    cast: Caster
    why: str = ""
    unit: str = ""
    validate: Validator | None = None

    def check(self, value: Any) -> str | None:
        return self.validate(value) if self.validate else None


def _positive(name: str) -> Validator:
    def check(value: Any) -> str | None:
        return None if value > 0 else f"{name} must be greater than zero"

    return check


def _in_range(name: str, low: float, high: float) -> Validator:
    def check(value: Any) -> str | None:
        if low <= value <= high:
            return None
        return f"{name} must be between {low} and {high}"

    return check


def _budget_list(raw: str) -> tuple[float, ...]:
    """Parse '100, 250, 500' (millions) into dollar amounts."""
    parts = [p.strip() for p in raw.replace(",", " ").split() if p.strip()]
    return tuple(float(p) * 1e6 for p in parts)


QUESTIONS: list[Question] = [
    Question(
        key="label",
        prompt="Name this scenario",
        default="",
        cast=str,
        why=(
            "This is how the run is identified later, so make it describe the "
            "choice you are testing — 'equal caps', 'academic-heavy', '$1B'. "
            "Leave blank and one is generated from the parameters."
        ),
    ),
    Question(
        key="budget_millions",
        prompt="Discretionary budget to allocate",
        default=500.0,
        cast=float,
        unit="$M",
        why=(
            "The total extra money on the table. The published scenario is "
            "$500M. Above roughly $510M the model runs out of places to put it, "
            "because every school hits its per-pupil cap."
        ),
        validate=_positive("budget"),
    ),
    Question(
        key="financial_weight",
        prompt="Weight on financial need (0-1); the rest goes to academic need",
        default=0.30,
        cast=float,
        why=(
            "1.0 reproduces the DOE's current practice of ranking on poverty "
            "alone. 0.0 ranks purely on test scores. The published model uses "
            "0.30, meaning 70% of the need score is academic."
        ),
        validate=_in_range("financial weight", 0.0, 1.0),
    ),
    Question(
        key="high_need_cap",
        prompt="Maximum extra funding for a high-need school",
        default=5000.0,
        cast=float,
        unit="$ per pupil",
        why=(
            "Without a cap the optimiser hands everything to one school. This "
            "is the ceiling that turns the model into a priority queue."
        ),
        validate=_positive("high-need cap"),
    ),
    Question(
        key="low_need_cap",
        prompt="Maximum extra funding for a lower-need school",
        default=1500.0,
        cast=float,
        unit="$ per pupil",
        why=(
            "Set this equal to the high-need cap to see what an equal-treatment "
            "policy would produce. The gap between the two caps is where most "
            "of the model's redistribution actually comes from."
        ),
        validate=_positive("lower-need cap"),
    ),
    Question(
        key="min_frpl_pct",
        prompt="Minimum FRPL share for a school to be eligible",
        default=60.0,
        cast=float,
        unit="%",
        why=(
            "The Title I eligibility floor. Lowering it widens the pool and "
            "dilutes every award; raising it concentrates the money."
        ),
        validate=_in_range("FRPL floor", 0.0, 100.0),
    ),
    Question(
        key="floor_score",
        prompt="Guarantee a minimum award to schools scoring below",
        default=60.0,
        cast=float,
        unit="Regents points",
        why=(
            "A political-feasibility constraint: no failing school should "
            "receive nothing. Set to 0 to switch the guarantee off."
        ),
        validate=_in_range("floor score", 0.0, 100.0),
    ),
    Question(
        key="floor_award",
        prompt="Size of that guaranteed minimum award",
        default=50000.0,
        cast=float,
        unit="$ total",
        why="Clipped to the school's own cap, so it can never create an infeasible bound.",
        validate=_in_range("floor award", 0.0, 1e9),
    ),
    Question(
        key="impact_factor",
        prompt="Regents points gained per $1 of extra per-pupil funding",
        default=0.001,
        cast=float,
        why=(
            "THE ASSUMPTION. 0.001 means $1,000 per pupil buys one point. It is "
            "not estimated from data. It scales every projected score but does "
            "not change the allocation or the ranking of scenarios, so leave it "
            "alone unless you are explicitly testing sensitivity to it."
        ),
        validate=_positive("impact factor"),
    ),
    Question(
        key="sweep_budgets",
        prompt="Budgets to test in the sensitivity sweep, in $M, space separated",
        default=(100e6, 250e6, 500e6, 750e6, 1000e6),
        cast=_budget_list,
        why=(
            "Used by the overlay charts to show how this scenario scales. Keep "
            "the same list across scenarios you intend to compare."
        ),
    ),
]


def _format_default(question: Question) -> str:
    value = question.default
    if question.key == "sweep_budgets":
        # No thousands separators: the displayed default must be valid input,
        # and the parser treats a comma as a separator between budgets.
        return " ".join(f"{v / 1e6:.0f}" for v in value)
    if isinstance(value, float):
        return f"{value:g}"
    return str(value) if value != "" else "auto"


def ask(
    question: Question,
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
) -> Any:
    """Prompt until the answer parses and validates."""
    if question.why:
        output_fn("")
        output_fn(f"  {question.why}")

    suffix = f" [{question.unit}]" if question.unit else ""
    prompt = f"{question.prompt}{suffix} ({_format_default(question)}): "

    while True:
        try:
            raw = input_fn(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            # Ctrl+D, Ctrl+C, or piped input that ran out: stop cleanly, not
            # with a traceback.
            raise WizardAborted("questionnaire aborted") from None
        if raw.lower() in {"q", "quit", "abort"}:
            raise WizardAborted("questionnaire aborted")
        if not raw:
            return question.default
        try:
            value = question.cast(raw)
        except (ValueError, TypeError):
            output_fn(f"  ! could not read {raw!r}; try again")
            continue
        problem = question.check(value)
        if problem:
            output_fn(f"  ! {problem}")
            continue
        return value


def collect_answers(
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
    answers: dict[str, Any] | None = None,
    questions: Sequence[Question] = tuple(QUESTIONS),
) -> dict[str, Any]:
    """Gather one answer per question.

    Any key present in ``answers`` is taken as given and not asked about, which
    is how the non-interactive and scripted paths work.
    """
    answers = dict(answers or {})
    collected: dict[str, Any] = {}

    for question in questions:
        if question.key in answers:
            value = question.cast(answers[question.key]) if isinstance(
                answers[question.key], str
            ) else answers[question.key]
            problem = question.check(value)
            if problem:
                raise ValueError(f"{question.key}: {problem}")
            collected[question.key] = value
            continue
        collected[question.key] = ask(question, input_fn, output_fn)
    return collected


def answers_to_config(answers: dict[str, Any]) -> ModelConfig:
    """Turn questionnaire answers into a validated :class:`ModelConfig`."""
    financial = float(answers["financial_weight"])
    return ModelConfig(
        min_frpl_pct=float(answers["min_frpl_pct"]),
        financial_weight=financial,
        academic_weight=1.0 - financial,
        extra_budget=float(answers["budget_millions"]) * 1e6,
        high_need_cap_per_pupil=float(answers["high_need_cap"]),
        low_need_cap_per_pupil=float(answers["low_need_cap"]),
        floor_score=float(answers["floor_score"]),
        floor_award=float(answers["floor_award"]),
        impact_factor=float(answers["impact_factor"]),
        sweep_budgets=tuple(answers["sweep_budgets"]),
    )


def summarise(config: ModelConfig, label: str) -> str:
    """A human-readable recap of the scenario about to be run."""
    lines = [
        f"  Scenario           {label or '(auto-generated)'}",
        f"  Budget             ${config.extra_budget / 1e6:,.0f}M",
        f"  Need index         {config.financial_weight:.0%} financial / "
        f"{config.academic_weight:.0%} academic",
        f"  Caps               ${config.high_need_cap_per_pupil:,.0f} high-need / "
        f"${config.low_need_cap_per_pupil:,.0f} lower-need, per pupil",
        f"  Eligibility        FRPL >= {config.min_frpl_pct:g}%",
        f"  Guaranteed award   ${config.floor_award:,.0f} below "
        f"{config.floor_score:g} Regents points",
        f"  Impact factor      {config.impact_factor:g} points per $/pupil",
        "  Sweep              "
        + ", ".join(f"${b / 1e6:,.0f}M" for b in config.sweep_budgets),
    ]
    return "\n".join(lines)


def save_config(config: ModelConfig, path: str | Path) -> Path:
    """Write the scenario to YAML so the run can be reproduced exactly."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = config.to_dict()
    payload["sweep_budgets"] = [float(b) for b in payload["sweep_budgets"]]

    with path.open("w", encoding="utf-8") as handle:
        handle.write("# Generated by `titlei wizard`. Safe to edit by hand.\n")
        yaml.safe_dump(payload, handle, sort_keys=False, default_flow_style=False)
    return path


def run_wizard(
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
    answers: dict[str, Any] | None = None,
) -> tuple[ModelConfig, str]:
    """Run the questionnaire and return the scenario it describes."""
    output_fn("")
    output_fn("Scenario setup — press Enter to accept a default, 'q' to abort.")

    collected = collect_answers(input_fn, output_fn, answers)
    config = answers_to_config(collected)
    label = str(collected.get("label") or "").strip()

    output_fn("")
    output_fn("Scenario:")
    output_fn(summarise(config, label))
    return config, label
