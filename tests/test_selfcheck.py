"""`titlei verify` is the onboarding contract: it must be honest about failure."""

from __future__ import annotations

import pytest

from titlei.selfcheck import (
    FAIL,
    PASS,
    SKIP,
    _first_sentence,
    run_checks,
    summarise,
)


@pytest.fixture(scope="module")
def healthy(tmp_path_factory):
    return run_checks(out_dir=tmp_path_factory.mktemp("out"))


def test_a_healthy_install_passes_everything(healthy):
    passed, failed, skipped = summarise(healthy)
    assert failed == 0
    assert passed >= 8


def test_the_golden_check_runs_in_a_checkout(healthy):
    """The check that proves the install reproduces the published analysis."""
    golden = [r for r in healthy if r.name == "Reproduces published results"]
    assert len(golden) == 1
    assert golden[0].status == PASS
    assert "0.00e+00" in golden[0].detail or "max difference $0" in golden[0].detail


def test_every_check_is_named_and_described(healthy):
    for result in healthy:
        assert result.name and result.detail
        assert result.status in {PASS, FAIL, SKIP}


def test_missing_data_fails_with_a_remedy(tmp_path):
    results = run_checks(data_path=tmp_path / "absent.csv", out_dir=tmp_path)
    data = next(r for r in results if r.name == "School data")

    assert data.status == FAIL
    assert data.remedy
    assert "absent.csv" in data.detail, "the file path must survive intact"


def test_later_checks_still_run_after_an_early_failure(tmp_path):
    """A broken data file must not hide whether the output directory works."""
    results = run_checks(data_path=tmp_path / "absent.csv", out_dir=tmp_path)
    assert any(r.name == "Output directory" for r in results)


def test_an_unwritable_output_directory_is_caught(tmp_path):
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("I am a file", encoding="utf-8")

    results = run_checks(out_dir=blocker)
    out = next(r for r in results if r.name == "Output directory")
    assert out.status == FAIL
    assert out.remedy


def test_a_bad_config_is_reported(tmp_path):
    config = tmp_path / "model.yaml"
    config.write_text("financial_weight: 0.9\nacademic_weight: 0.9\n")

    results = run_checks(config_path=config, out_dir=tmp_path)
    entry = next(r for r in results if r.name == "Configuration")
    assert entry.status == FAIL


def test_golden_check_skips_on_a_non_published_budget(tmp_path):
    config = tmp_path / "model.yaml"
    config.write_text("extra_budget: 250000000\n")

    results = run_checks(config_path=config, out_dir=tmp_path)
    golden = next(r for r in results if r.name == "Reproduces published results")
    assert golden.status == SKIP
    assert "250M" in golden.detail


def test_failures_do_not_raise(tmp_path):
    """Verify reports problems; it never explodes on them."""
    config = tmp_path / "model.yaml"
    config.write_text("high_need_cap_per_pupil: 100\nlow_need_cap_per_pupil: 5000\n")
    results = run_checks(config_path=config, out_dir=tmp_path)
    assert any(r.status == FAIL for r in results)


@pytest.mark.parametrize(
    "message, expected",
    [
        ("school data not found at /tmp/a.csv. See README.", "school data not found at /tmp/a.csv"),
        ("plain message", "plain message"),
        ("first. second", "first"),
        ("/a/b.csv is bad", "/a/b.csv is bad"),
    ],
)
def test_first_sentence_does_not_truncate_file_paths(message, expected):
    assert _first_sentence(message) == expected


def test_summarise_counts_each_status(healthy):
    passed, failed, skipped = summarise(healthy)
    assert passed + failed + skipped == len(healthy)
