from __future__ import annotations

import pandas as pd
import pytest

from titlei.data import MODEL_COLUMNS, load_raw, prepare, validate


def test_eligible_schools_load(schools):
    assert len(schools) == 349
    assert not schools[MODEL_COLUMNS].isna().any().any()
    assert (schools["K-12 Enrollment"] > 0).all()


def test_frpl_floor_is_enforced(config, schools):
    assert (schools["FRPL %"] >= config.min_frpl_pct).all()


def test_percentage_strings_are_coerced(tiny_schools, config):
    tiny_schools["FRPL %"] = ["95%", "85%", "70%", "60%"]
    prepared, _ = prepare(tiny_schools, config)
    assert len(prepared) == 4
    assert pd.api.types.is_numeric_dtype(prepared["FRPL %"])
    assert prepared["FRPL %"].tolist() == [95, 85, 70, 60]


def test_rows_below_the_floor_are_reported(tiny_schools, config):
    tiny_schools.loc[3, "FRPL %"] = 10.0
    prepared, report = prepare(tiny_schools, config)
    assert len(prepared) == 3
    assert report.dropped_below_frpl_floor == 1
    assert "1 below FRPL floor" in report.summary()


def test_zero_enrollment_is_dropped(tiny_schools, config):
    tiny_schools.loc[0, "K-12 Enrollment"] = 0
    prepared, report = prepare(tiny_schools, config)
    assert report.dropped_zero_enrollment == 1
    assert "Alpha" not in set(prepared["School Name"])


def test_missing_columns_raise():
    with pytest.raises(ValueError, match="missing required columns"):
        validate(pd.DataFrame({"School Name": ["Alpha"]}))


def test_empty_frame_raises(tiny_schools):
    with pytest.raises(ValueError, match="empty"):
        validate(tiny_schools.iloc[0:0])


def test_missing_file_raises_with_guidance(tmp_path):
    with pytest.raises(FileNotFoundError, match="data/README.md"):
        load_raw(tmp_path / "nope.csv")
