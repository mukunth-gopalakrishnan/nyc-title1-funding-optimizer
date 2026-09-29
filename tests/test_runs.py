"""The registry's job is that two runs are never confused for each other."""

from __future__ import annotations

import datetime as dt

import pytest

from titlei.config import ModelConfig
from titlei.pipeline import run_pipeline
from titlei.runs import (
    AmbiguousRunReference,
    RunNotFound,
    RunRegistry,
    config_hash,
)


@pytest.fixture(scope="module")
def results():
    """Three genuinely different scenarios."""
    base = ModelConfig()
    return {
        "control": run_pipeline(config=base, with_sweep=False),
        "half": run_pipeline(config=base.replace(extra_budget=250e6), with_sweep=False),
        "financial": run_pipeline(
            config=base.replace(financial_weight=1.0, academic_weight=0.0),
            with_sweep=False,
        ),
    }


@pytest.fixture
def registry(tmp_path, results):
    registry = RunRegistry(tmp_path / "runs")
    registry.save(results["control"], "Control", make_control=True)
    registry.save(results["half"], "Half budget")
    registry.save(results["financial"], "Financial only")
    return registry


def test_config_hash_is_stable_and_discriminating():
    a = ModelConfig()
    assert config_hash(a) == config_hash(ModelConfig())
    assert config_hash(a) != config_hash(a.replace(extra_budget=1.0))


def test_run_id_carries_the_parameter_fingerprint(registry, results):
    record = registry.resolve("Control")
    assert record.run_id.endswith(config_hash(results["control"].config))


def test_every_run_stores_the_parameters_that_produced_it(registry, results):
    for label, key in (("Control", "control"), ("Half budget", "half")):
        assert registry.resolve(label).config == results[key].config


def test_runs_survive_a_round_trip_to_disk(tmp_path, results):
    written = RunRegistry(tmp_path / "runs").save(results["control"], "Control")
    reread = RunRegistry(tmp_path / "runs").resolve(written.run_id)

    assert reread.config == written.config
    assert reread.label == written.label
    assert reread.roi == pytest.approx(written.roi)
    assert len(reread.allocation) == 349


def test_table_lists_one_row_per_run_with_its_parameters(registry):
    table = registry.table()
    assert len(table) == 3
    assert set(table["budget"]) == {500e6, 250e6}
    assert table["control"].sum() == 1


def test_runs_with_different_parameters_are_distinguishable(registry):
    table = registry.table().set_index("label")
    assert table.loc["Half budget", "budget"] == 250e6
    assert table.loc["Financial only", "financial_weight"] == 1.0
    assert table.loc["Control", "financial_weight"] == 0.3
    assert table["config_hash"].nunique() == 3


def test_resolve_accepts_id_prefix_hash_and_label(registry):
    record = registry.resolve("Control")
    assert registry.resolve(record.run_id).run_id == record.run_id
    # A prefix must reach into the parameter hash to be unambiguous when
    # several runs land in the same second.
    assert registry.resolve(record.run_id[:-2]).run_id == record.run_id
    assert registry.resolve(record.config_hash).run_id == record.run_id


def test_unknown_reference_raises(registry):
    with pytest.raises(RunNotFound):
        registry.resolve("no-such-run")


def test_ambiguous_prefix_raises(tmp_path, results):
    registry = RunRegistry(tmp_path / "runs")
    now = dt.datetime(2026, 1, 1, 12, 0, 0)
    registry.save(results["control"], "A", now=now)
    registry.save(results["half"], "B", now=now.replace(second=1))
    with pytest.raises(AmbiguousRunReference):
        registry.resolve("2026")


def test_first_run_becomes_the_control(tmp_path, results):
    registry = RunRegistry(tmp_path / "runs")
    first = registry.save(results["half"], "First")
    registry.save(results["control"], "Second")
    assert registry.control.run_id == first.run_id


def test_control_can_be_reassigned(registry):
    record = registry.resolve("Half budget")
    registry.set_control(record.label)
    assert registry.control.run_id == record.run_id


def test_deleting_the_control_promotes_another_run(registry):
    control = registry.control
    registry.delete(control.run_id)
    assert registry.control is not None
    assert registry.control.run_id != control.run_id
    assert len(registry.list()) == 2


def test_empty_registry_is_not_an_error(tmp_path):
    registry = RunRegistry(tmp_path / "nothing-here")
    assert registry.list() == []
    assert registry.control is None
    assert registry.table().empty
    with pytest.raises(RunNotFound, match="empty"):
        registry.resolve("anything")


def test_auto_label_describes_the_scenario(tmp_path, results):
    record = RunRegistry(tmp_path / "runs").save(results["half"])
    assert "$250M" in record.label
    assert "30%/70%" in record.label


# --- replacing runs a caller owns -------------------------------------------


def test_delete_by_label_removes_every_match(tmp_path, results):
    registry = RunRegistry(tmp_path / "runs")
    registry.save(results["control"], "Repeated")
    registry.save(results["half"], "Repeated")
    registry.save(results["financial"], "Kept")

    removed = registry.delete_by_label("Repeated")
    assert len(removed) == 2
    assert [r.label for r in registry.list()] == ["Kept"]


def test_delete_by_label_is_a_no_op_when_nothing_matches(tmp_path, results):
    registry = RunRegistry(tmp_path / "runs")
    registry.save(results["control"], "Only")
    assert registry.delete_by_label("absent") == []
    assert len(registry.list()) == 1


def test_deleting_the_control_by_label_promotes_another_run(tmp_path, results):
    registry = RunRegistry(tmp_path / "runs")
    registry.save(results["control"], "Control", make_control=True)
    registry.save(results["half"], "Other")

    registry.delete_by_label("Control")
    assert registry.control is not None
    assert registry.control.label == "Other"


def test_replacing_keeps_a_label_unambiguous(tmp_path, results):
    """The failure this exists to prevent: lookup by name breaking on a repeat."""
    registry = RunRegistry(tmp_path / "runs")
    registry.save(results["control"], "Nightly")
    registry.delete_by_label("Nightly")
    registry.save(results["half"], "Nightly")

    assert registry.resolve("Nightly").config.extra_budget == 250e6
