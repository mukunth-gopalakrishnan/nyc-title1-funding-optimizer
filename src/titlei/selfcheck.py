"""Self-check: prove the installation works, without running the test suite.

`pytest` is the right tool for a developer. It is the wrong tool for someone
who has just cloned the repository to look at the analysis — they should not
need to know what a fixture is to find out whether the thing runs.

`titlei verify` walks the same path the model does, one stage at a time, and
says which stage broke and what to do about it. Every check is independent, so
a failure early on does not hide what is working later.

The project imports in this module are deliberately deferred into the check
functions rather than hoisted to the top. A missing dependency or a malformed
config must be *reported* by the relevant check, not raised while this module
is being imported — otherwise `titlei verify`, the command whose entire job is
diagnosing a broken install, would itself fail to load.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from titlei.resources import GOLDEN_FILE as _GOLDEN

PASS = "pass"
FAIL = "fail"
SKIP = "skip"

MIN_PYTHON = (3, 9)
REQUIRED_PACKAGES = ("pandas", "numpy", "scipy", "matplotlib", "yaml")

#: The published per-school results. Bundled inside the package, so even a
#: downloaded binary can prove it reproduces the original analysis.
GOLDEN_FILE = _GOLDEN


@dataclass
class CheckResult:
    """One verification step and what it found."""

    name: str
    status: str
    detail: str
    remedy: str = ""

    @property
    def ok(self) -> bool:
        return self.status != FAIL

    def line(self) -> str:
        mark = {PASS: "PASS", FAIL: "FAIL", SKIP: "SKIP"}[self.status]
        return f"  [{mark}] {self.name:<34} {self.detail}"


def _first_sentence(message: str) -> str:
    """The first sentence of an exception message, without eating file paths.

    Splitting on "." alone truncates ``/tmp/schools.csv`` to ``/tmp/schools``,
    so only a period followed by whitespace ends a sentence here.
    """
    first_line = message.strip().splitlines()[0]
    for index, char in enumerate(first_line[:-1]):
        if char == "." and first_line[index + 1].isspace():
            return first_line[:index]
    return first_line


def _check_python() -> CheckResult:
    version = ".".join(str(p) for p in sys.version_info[:3])
    if sys.version_info[:2] >= MIN_PYTHON:
        return CheckResult("Python version", PASS, f"{version}")
    return CheckResult(
        "Python version",
        FAIL,
        f"{version} is older than {'.'.join(map(str, MIN_PYTHON))}",
        "Install a newer Python and recreate the virtual environment.",
    )


def _check_packages() -> CheckResult:
    missing = []
    for package in REQUIRED_PACKAGES:
        try:
            importlib.import_module(package)
        except ImportError:
            missing.append(package)
    if not missing:
        return CheckResult(
            "Dependencies", PASS, f"all {len(REQUIRED_PACKAGES)} importable"
        )
    return CheckResult(
        "Dependencies",
        FAIL,
        f"missing: {', '.join(missing)}",
        'Run: pip install -e ".[dev,dashboard]"',
    )


def _check_config(config_path: str | Path | None) -> tuple[CheckResult, object | None]:
    """Load the config once. Everything downstream reuses the result.

    Reloading it in each check would let an invalid config raise out of
    ``run_checks`` instead of being reported, which is precisely the failure
    this command exists to catch.
    """
    from titlei.config import load_config

    try:
        config = load_config(config_path)
    except Exception as exc:  # malformed YAML, or an invalid combination
        return (
            CheckResult(
                "Configuration",
                FAIL,
                _first_sentence(str(exc)),
                "Fix config/model.yaml; see docs/methodology.md for what each knob does.",
            ),
            None,
        )
    return (
        CheckResult(
            "Configuration",
            PASS,
            f"${config.extra_budget / 1e6:,.0f}M budget, "
            f"{config.financial_weight:.0%}/{config.academic_weight:.0%} need index",
        ),
        config,
    )


def _check_data(
    data_path: str | Path | None, config=None
) -> tuple[CheckResult, object | None]:
    from titlei.data import load_schools

    try:
        schools, report = load_schools(data_path, config)
    except FileNotFoundError as exc:
        return (
            CheckResult(
                "School data",
                FAIL,
                _first_sentence(str(exc)),
                "See data/README.md for how to regenerate the CSV.",
            ),
            None,
        )
    except ValueError as exc:
        return (
            CheckResult("School data", FAIL, str(exc), "The CSV is missing columns."),
            None,
        )

    if schools.empty:
        return (
            CheckResult(
                "School data",
                FAIL,
                "no schools survived the eligibility filter",
                "Lower min_frpl_pct, or check the FRPL % column.",
            ),
            None,
        )
    return (
        CheckResult("School data", PASS, report.summary()),
        schools,
    )


def _check_model(schools, config) -> Iterator[CheckResult]:
    """Score need, solve the LP, and project outcomes — the whole path."""
    from titlei.needs import HIGH_NEED, NEED_GROUP
    from titlei.optimizer import InfeasibleAllocation
    from titlei.simulate import CHANGE, FUNDING, run_scenario

    try:
        frame, allocation = run_scenario(schools, config, strategy="combined")
    except InfeasibleAllocation as exc:
        yield CheckResult(
            "Allocation solves",
            FAIL,
            str(exc),
            "Raise the budget or lower the guaranteed floor award.",
        )
        return
    except Exception as exc:
        yield CheckResult(
            "Allocation solves", FAIL, f"{type(exc).__name__}: {exc}",
            "This is a bug — please open an issue with this output.",
        )
        return

    tiers = frame[NEED_GROUP].value_counts()
    yield CheckResult(
        "Need scoring",
        PASS if len(tiers) == 2 else FAIL,
        f"{tiers.get(HIGH_NEED, 0)} high-need, "
        f"{tiers.sum() - tiers.get(HIGH_NEED, 0)} lower-need",
        "" if len(tiers) == 2 else "Every school landed in one tier; check weight_floor.",
    )

    within_budget = allocation.budget_used <= config.extra_budget + 1e-6
    yield CheckResult(
        "Allocation solves",
        PASS if within_budget else FAIL,
        f"${allocation.budget_used:,.0f} across "
        f"{allocation.schools_funded} schools",
        "" if within_budget else "The solver exceeded the budget — this is a bug.",
    )

    no_losers = bool((frame[CHANGE] >= -1e-9).all())
    funded_only = bool((frame.loc[frame[FUNDING] <= 0, CHANGE].abs() < 1e-9).all())
    yield CheckResult(
        "Outcome projection",
        PASS if (no_losers and funded_only) else FAIL,
        f"mean +{frame[CHANGE].mean():.2f} Regents points",
        "" if no_losers else "A school lost ground — the impact model is wrong.",
    )


def _check_golden(schools, config) -> CheckResult:
    """The strongest check: does this install reproduce the published numbers?"""
    fixture = GOLDEN_FILE
    if not fixture.exists():
        return CheckResult(
            "Reproduces published results",
            SKIP,
            "published results file is missing from this installation",
        )

    import numpy as np
    import pandas as pd

    from titlei.simulate import FUNDING, run_scenario

    if config.extra_budget != 500_000_000.0:
        return CheckResult(
            "Reproduces published results",
            SKIP,
            f"config budget is ${config.extra_budget / 1e6:,.0f}M, not the published $500M",
        )

    frame, _ = run_scenario(schools, config, strategy="combined")
    golden = pd.read_csv(fixture)
    merged = frame.merge(golden, on="School Name")

    if len(merged) != len(golden):
        return CheckResult(
            "Reproduces published results",
            FAIL,
            f"{len(merged)} of {len(golden)} schools matched by name",
            "The data file does not match the one the analysis was published from.",
        )

    difference = float(
        np.abs(merged[FUNDING] - merged["Optimized_Funding_500M"]).max()
    )
    if difference <= 1e-6:
        return CheckResult(
            "Reproduces published results",
            PASS,
            f"max difference ${difference:.2e} across {len(merged)} schools",
        )
    return CheckResult(
        "Reproduces published results",
        FAIL,
        f"max difference ${difference:,.2f}",
        "The model no longer matches the original analysis.",
    )


def _check_writable(out_dir: str | Path) -> CheckResult:
    path = Path(out_dir)
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".titlei-write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return CheckResult(
            "Output directory", FAIL, f"{path} is not writable ({exc.strerror})",
            "Pass a writable path with --out.",
        )
    return CheckResult("Output directory", PASS, f"{path} is writable")


def run_checks(
    data_path: str | Path | None = None,
    config_path: str | Path | None = None,
    out_dir: str | Path = "outputs",
) -> list[CheckResult]:
    """Run every check in order and return the results."""
    results = [_check_python(), _check_packages()]
    if not results[-1].ok:
        return results  # nothing below this can run

    config_result, config = _check_config(config_path)
    results.append(config_result)

    data_result, schools = _check_data(data_path, config)
    results.append(data_result)

    if schools is not None and config is not None:
        results.extend(_check_model(schools, config))
        results.append(_check_golden(schools, config))

    results.append(_check_writable(out_dir))
    return results


def summarise(results: list[CheckResult]) -> tuple[int, int, int]:
    """Return (passed, failed, skipped)."""
    passed = sum(r.status == PASS for r in results)
    failed = sum(r.status == FAIL for r in results)
    skipped = sum(r.status == SKIP for r in results)
    return passed, failed, skipped
