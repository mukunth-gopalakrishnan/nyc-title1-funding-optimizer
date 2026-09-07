"""A registry of simulation runs, so results are never anonymous.

Every run is written to its own directory carrying the **full parameter set
that produced it**, a content hash of those parameters, a timestamp and a
human label. Two runs with different budgets can never be confused, and two
runs with identical parameters are recognisable as repeats by their shared
``config_hash``.

One run in the registry is the **control**: the reference every comparison is
measured against. By default that is the published $500M scenario. Deltas in
:func:`titlei.compare.comparison_table` are always "versus control", so a
sweep of a dozen scenarios still has a fixed point.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from titlei.config import ModelConfig
from titlei.pipeline import PipelineResult

logger = logging.getLogger(__name__)

DEFAULT_RUNS_DIR = Path("runs")
INDEX_FILE = "index.json"
MANIFEST_FILE = "manifest.json"

_LABEL_SAFE = re.compile(r"[^a-z0-9]+")


class RunNotFound(KeyError):
    """Raised when a run reference matches no run in the registry."""


class AmbiguousRunReference(KeyError):
    """Raised when a run reference matches more than one run."""


def config_hash(config: ModelConfig) -> str:
    """A short, stable fingerprint of a parameter set.

    Identical parameters always produce the same hash, so a repeat run is
    obvious even when its label and timestamp differ.
    """
    payload = json.dumps(config.to_dict(), sort_keys=True, default=list)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8]


def slugify(text: str) -> str:
    return _LABEL_SAFE.sub("-", text.lower()).strip("-") or "run"


@dataclass
class RunRecord:
    """One simulation run, plus the parameters that produced it."""

    run_id: str
    label: str
    created_at: str
    config: ModelConfig
    config_hash: str
    headline: dict[str, float]
    roi: dict[str, float]
    load_summary: str
    notes: str = ""
    directory: Path | None = None
    _frames: dict[str, pd.DataFrame] = field(default_factory=dict, repr=False)

    # --- stored tables, read on first use --------------------------------
    def _frame(self, name: str) -> pd.DataFrame:
        if name not in self._frames:
            if self.directory is None:
                raise FileNotFoundError(f"run {self.run_id} has no directory on disk")
            path = self.directory / f"{name}.csv"
            if not path.exists():
                self._frames[name] = pd.DataFrame()
            else:
                self._frames[name] = pd.read_csv(path)
        return self._frames[name]

    @property
    def allocation(self) -> pd.DataFrame:
        """Per-school results for the proposed (combined-need) strategy."""
        return self._frame("allocation")

    @property
    def group_summary(self) -> pd.DataFrame:
        return self._frame("group_summary")

    @property
    def sweep(self) -> pd.DataFrame:
        return self._frame("budget_sweep")

    # --- serialisation ---------------------------------------------------
    def to_manifest(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "label": self.label,
            "created_at": self.created_at,
            "config_hash": self.config_hash,
            "config": self.config.to_dict(),
            "headline": self.headline,
            "roi": self.roi,
            "load_summary": self.load_summary,
            "notes": self.notes,
        }

    @classmethod
    def from_manifest(cls, payload: dict[str, Any], directory: Path) -> RunRecord:
        config_payload = dict(payload["config"])
        if isinstance(config_payload.get("sweep_budgets"), list):
            config_payload["sweep_budgets"] = tuple(config_payload["sweep_budgets"])
        return cls(
            run_id=payload["run_id"],
            label=payload["label"],
            created_at=payload["created_at"],
            config=ModelConfig(**config_payload),
            config_hash=payload["config_hash"],
            headline=payload["headline"],
            roi=payload["roi"],
            load_summary=payload.get("load_summary", ""),
            notes=payload.get("notes", ""),
            directory=directory,
        )

    def index_row(self) -> dict[str, Any]:
        """The one-line view of this run used by listings and comparisons."""
        config = self.config
        return {
            "run_id": self.run_id,
            "label": self.label,
            "created_at": self.created_at,
            "config_hash": self.config_hash,
            "budget": config.extra_budget,
            "financial_weight": config.financial_weight,
            "academic_weight": config.academic_weight,
            "high_need_cap": config.high_need_cap_per_pupil,
            "low_need_cap": config.low_need_cap_per_pupil,
            "min_frpl_pct": config.min_frpl_pct,
            "impact_factor": config.impact_factor,
            "budget_used": self.roi.get("budget_used", float("nan")),
            "schools_funded": self.headline.get("schools_funded", float("nan")),
            "students_reached": self.headline.get("students_reached", float("nan")),
            "mean_score_change": self.headline.get("mean_score_change", float("nan")),
            "gap_after": self.headline.get("gap_after", float("nan")),
            "gap_closed": self.roi.get("gap_closed", float("nan")),
            "academic_gap_closed": self.roi.get("academic_gap_closed", float("nan")),
            "academic_gap_closed_per_100m": self.roi.get(
                "academic_gap_closed_per_100m", float("nan")
            ),
            "high_need_share_of_budget": self.roi.get(
                "high_need_share_of_budget", float("nan")
            ),
            "high_need_share_of_points": self.roi.get(
                "high_need_share_of_points", float("nan")
            ),
            "bottom_quartile_mean_gain": self.roi.get(
                "bottom_quartile_mean_gain", float("nan")
            ),
        }


class RunRegistry:
    """A directory of saved runs, with one of them marked as the control."""

    def __init__(self, root: str | Path = DEFAULT_RUNS_DIR):
        self.root = Path(root)

    # --- index -----------------------------------------------------------
    @property
    def index_path(self) -> Path:
        return self.root / INDEX_FILE

    def _read_index(self) -> dict[str, Any]:
        if not self.index_path.exists():
            return {"control": None}
        with self.index_path.open(encoding="utf-8") as handle:
            return json.load(handle)

    def _write_index(self, payload: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.index_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    # --- writing ---------------------------------------------------------
    def save(
        self,
        result: PipelineResult,
        label: str | None = None,
        *,
        notes: str = "",
        make_control: bool = False,
        now: dt.datetime | None = None,
    ) -> RunRecord:
        """Persist ``result`` with the parameters that produced it."""
        now = now or dt.datetime.now()
        digest = config_hash(result.config)
        label = label or self._auto_label(result.config)
        run_id = f"{now:%Y%m%d-%H%M%S}-{digest}"

        directory = self.root / run_id
        directory.mkdir(parents=True, exist_ok=True)

        record = RunRecord(
            run_id=run_id,
            label=label,
            created_at=now.isoformat(timespec="seconds"),
            config=result.config,
            config_hash=digest,
            headline=result.headline,
            roi=result.roi,
            load_summary=result.load_report.summary(),
            notes=notes,
            directory=directory,
        )

        result.combined.to_csv(directory / "allocation.csv", index=False)
        result.naive.to_csv(directory / "baseline_allocation.csv", index=False)
        result.group_summary.to_csv(directory / "group_summary.csv", index=False)
        if not result.sweep.empty:
            result.sweep.to_csv(directory / "budget_sweep.csv", index=False)

        with (directory / MANIFEST_FILE).open("w", encoding="utf-8") as handle:
            json.dump(record.to_manifest(), handle, indent=2)

        index = self._read_index()
        if make_control or index.get("control") is None:
            index["control"] = run_id
        self._write_index(index)

        logger.info("saved run %s (%s)", run_id, label)
        return record

    @staticmethod
    def _auto_label(config: ModelConfig) -> str:
        """A label that describes the scenario when the user gives none."""
        return (
            f"${config.extra_budget / 1e6:,.0f}M · "
            f"{config.financial_weight:.0%}/{config.academic_weight:.0%} fin/acad · "
            f"caps {config.high_need_cap_per_pupil:,.0f}/"
            f"{config.low_need_cap_per_pupil:,.0f}"
        )

    # --- reading ---------------------------------------------------------
    def list(self) -> list[RunRecord]:
        """Every saved run, newest first."""
        if not self.root.exists():
            return []
        records = []
        for directory in sorted(self.root.iterdir()):
            manifest = directory / MANIFEST_FILE
            if not directory.is_dir() or not manifest.exists():
                continue
            with manifest.open(encoding="utf-8") as handle:
                records.append(RunRecord.from_manifest(json.load(handle), directory))
        return sorted(records, key=lambda r: r.created_at, reverse=True)

    def resolve(self, reference: str) -> RunRecord:
        """Find a run by id, id prefix, config hash, or exact label."""
        records = self.list()
        if not records:
            raise RunNotFound("the registry is empty; run `titlei run` first")

        for match in (
            [r for r in records if r.run_id == reference],
            [r for r in records if r.label == reference],
            [r for r in records if r.run_id.startswith(reference)],
            [r for r in records if r.config_hash == reference],
        ):
            if len(match) == 1:
                return match[0]
            if len(match) > 1:
                ids = ", ".join(r.run_id for r in match)
                raise AmbiguousRunReference(
                    f"{reference!r} matches several runs: {ids}"
                )
        raise RunNotFound(f"no run matches {reference!r}")

    def resolve_all(self, references: Iterable[str]) -> list[RunRecord]:
        return [self.resolve(reference) for reference in references]

    @property
    def control(self) -> RunRecord | None:
        """The run every comparison is measured against."""
        control_id = self._read_index().get("control")
        if not control_id:
            return None
        try:
            return self.resolve(control_id)
        except RunNotFound:
            return None

    def set_control(self, reference: str) -> RunRecord:
        record = self.resolve(reference)
        index = self._read_index()
        index["control"] = record.run_id
        self._write_index(index)
        return record

    def table(self) -> pd.DataFrame:
        """Every run as one row — the "which run was which" listing."""
        records = self.list()
        if not records:
            return pd.DataFrame()
        control = self._read_index().get("control")
        frame = pd.DataFrame([r.index_row() for r in records])
        frame.insert(1, "control", frame["run_id"] == control)
        return frame

    def delete(self, reference: str) -> str:
        """Remove one run from the registry. Returns the deleted run id."""
        import shutil

        record = self.resolve(reference)
        if record.directory is None:
            raise RunNotFound(f"run {record.run_id} has no directory to delete")
        shutil.rmtree(record.directory)

        index = self._read_index()
        if index.get("control") == record.run_id:
            remaining = self.list()
            index["control"] = remaining[-1].run_id if remaining else None
            self._write_index(index)
        return record.run_id
