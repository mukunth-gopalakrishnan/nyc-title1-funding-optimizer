"""Loading, cleaning and validating the school-level source table."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from titlei.config import ModelConfig
from titlei.resources import DATA_FILE

logger = logging.getLogger(__name__)

DEFAULT_DATA_PATH = DATA_FILE

SCHOOL = "School Name"
SCORE = "Avg Regents Score"
ENROLLMENT = "K-12 Enrollment"
FRPL_COUNT = "K-12 FRPL Count"
FRPL_PCT = "FRPL %"
FUNDING_PER_PUPIL = "Total School Funding per Pupil"

MODEL_COLUMNS = [SCHOOL, SCORE, ENROLLMENT, FRPL_COUNT, FUNDING_PER_PUPIL]
CONTEXT_COLUMNS = ["School DBN", "District", "Borough"]


@dataclass
class LoadReport:
    """What the loader had to throw away to get to a modellable table."""

    rows_in: int
    rows_out: int
    dropped_below_frpl_floor: int
    dropped_missing_fields: int
    dropped_zero_enrollment: int

    def summary(self) -> str:
        return (
            f"{self.rows_out} of {self.rows_in} schools retained "
            f"(-{self.dropped_below_frpl_floor} below FRPL floor, "
            f"-{self.dropped_missing_fields} missing model fields, "
            f"-{self.dropped_zero_enrollment} zero enrollment)"
        )


def _to_numeric(series: pd.Series) -> pd.Series:
    """Coerce a column that may carry '%' signs or thousands separators."""
    if series.dtype.kind in "if":
        return series
    cleaned = (
        series.astype(str)
        .str.replace("%", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.strip()
    )
    return pd.to_numeric(cleaned, errors="coerce")


def load_raw(path: str | Path | None = None) -> pd.DataFrame:
    """Read the raw school table without applying any model filters."""
    path = Path(path) if path is not None else DEFAULT_DATA_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"school data not found at {path}. See data/README.md for how to "
            "regenerate it from the source workbook."
        )
    frame = pd.read_csv(path)
    frame.columns = [c.strip() for c in frame.columns]
    return frame


def validate(frame: pd.DataFrame) -> None:
    """Fail loudly if the source table is missing anything the model needs."""
    missing = [c for c in MODEL_COLUMNS + [FRPL_PCT] if c not in frame.columns]
    if missing:
        raise ValueError(f"school data is missing required columns: {missing}")
    if frame.empty:
        raise ValueError("school data is empty")
    duplicates = frame[SCHOOL].duplicated().sum()
    if duplicates:
        logger.warning("%d duplicate school names in source data", duplicates)


def prepare(
    frame: pd.DataFrame, config: ModelConfig | None = None
) -> tuple[pd.DataFrame, LoadReport]:
    """Clean the raw table down to the eligible, fully-populated model frame."""
    config = config or ModelConfig()
    validate(frame)
    rows_in = len(frame)

    frame = frame.copy()
    for column in (SCORE, ENROLLMENT, FRPL_COUNT, FRPL_PCT, FUNDING_PER_PUPIL):
        frame[column] = _to_numeric(frame[column])

    eligible = frame[frame[FRPL_PCT] >= config.min_frpl_pct]
    dropped_frpl = rows_in - len(eligible)

    keep = [c for c in CONTEXT_COLUMNS if c in eligible.columns] + MODEL_COLUMNS + [FRPL_PCT]
    model_frame = eligible[keep].dropna(subset=MODEL_COLUMNS)
    dropped_missing = len(eligible) - len(model_frame)

    positive = model_frame[model_frame[ENROLLMENT] > 0].reset_index(drop=True)
    dropped_zero = len(model_frame) - len(positive)

    report = LoadReport(
        rows_in=rows_in,
        rows_out=len(positive),
        dropped_below_frpl_floor=dropped_frpl,
        dropped_missing_fields=dropped_missing,
        dropped_zero_enrollment=dropped_zero,
    )
    logger.info(report.summary())
    return positive, report


def load_schools(
    path: str | Path | None = None, config: ModelConfig | None = None
) -> tuple[pd.DataFrame, LoadReport]:
    """Convenience wrapper: read the raw table and prepare it in one call."""
    return prepare(load_raw(path), config)
