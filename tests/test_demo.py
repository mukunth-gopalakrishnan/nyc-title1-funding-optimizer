"""The demo is what a new user runs first; it must work with zero arguments."""

from __future__ import annotations

import pytest

from titlei.demo import run_demo


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    root = tmp_path_factory.mktemp("demo")
    lines: list[str] = []
    result = run_demo(
        out_dir=root / "out",
        runs_dir=root / "runs",
        emit=lines.append,
        build_html=True,
    )
    return result, lines, root


def test_demo_runs_both_scenarios_and_registers_them(demo):
    result, _, root = demo
    assert result["proposed"].run_id != result["baseline"].run_id
    assert result["proposed"].config.financial_weight == 0.3
    assert result["baseline"].config.financial_weight == 1.0
    assert (root / "runs").is_dir()


def test_demo_writes_every_artefact(demo):
    result, _, _ = demo
    assert result["report"].exists()
    assert len(result["charts"]) == 5
    assert result["tables"]
    for path in result["charts"].values():
        assert path.stat().st_size > 0


def test_demo_narrates_each_step_with_its_command(demo):
    _, lines, _ = demo
    text = "\n".join(lines)
    for step in range(1, 6):
        assert f"Step {step} —" in text
    for command in ("titlei describe", "titlei run", "titlei compare", "titlei report"):
        assert command in text


def test_demo_warns_about_the_invariance(demo):
    """A new user must not read the comparison as an efficiency result."""
    _, lines, _ = demo
    text = "\n".join(lines).lower()
    assert "identical for both" in text
    assert "only targeting differs" in text


def test_demo_reports_the_real_headline_numbers(demo):
    result, lines, _ = demo
    text = "\n".join(lines)
    assert "349 schools" in text
    assert "210,396 students" in text
    assert result["mean_gain"] == pytest.approx(3.1535576789, abs=1e-6)


def test_demo_tells_the_user_what_to_do_next(demo):
    _, lines, _ = demo
    text = "\n".join(lines)
    assert "What to do next" in text
    assert "titlei wizard" in text


def test_demo_works_without_building_the_report(tmp_path):
    result = run_demo(
        out_dir=tmp_path / "out",
        runs_dir=tmp_path / "runs",
        emit=lambda _: None,
        build_html=False,
    )
    assert result["report"] is None
    assert len(result["charts"]) == 5


def test_demo_is_idempotent(tmp_path):
    """Running the demo twice must not make its own labels ambiguous.

    The demo tells the user to run `titlei show '<label>'`, so a duplicate
    label breaks the very next thing they type.
    """
    from titlei.demo import BASELINE_LABEL, PROPOSED_LABEL
    from titlei.runs import RunRegistry

    runs = tmp_path / "runs"
    for _ in range(2):
        run_demo(
            out_dir=tmp_path / "out", runs_dir=runs,
            emit=lambda _: None, build_html=False,
        )

    registry = RunRegistry(runs)
    assert len(registry.list()) == 2
    # Neither of these may raise AmbiguousRunReference.
    assert registry.resolve(PROPOSED_LABEL).config.financial_weight == 0.3
    assert registry.resolve(BASELINE_LABEL).config.financial_weight == 1.0
