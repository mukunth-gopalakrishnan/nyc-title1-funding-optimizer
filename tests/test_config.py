from __future__ import annotations

import pytest
import yaml

from titlei.config import DEFAULT_CONFIG_PATH, ModelConfig, load_config


def test_default_config_matches_shipped_yaml():
    """The dataclass defaults and config/model.yaml must not drift apart."""
    from_yaml = load_config(DEFAULT_CONFIG_PATH)
    assert from_yaml == ModelConfig()


def test_need_weights_must_sum_to_one():
    with pytest.raises(ValueError, match="must sum to 1.0"):
        ModelConfig(financial_weight=0.5, academic_weight=0.7)


def test_low_need_cap_cannot_exceed_high_need_cap():
    with pytest.raises(ValueError, match="cannot exceed"):
        ModelConfig(high_need_cap_per_pupil=1000, low_need_cap_per_pupil=2000)


def test_replace_returns_a_new_validated_config(config):
    tweaked = config.replace(extra_budget=1_000.0)
    assert tweaked.extra_budget == 1_000.0
    assert config.extra_budget != 1_000.0
    with pytest.raises(ValueError):
        config.replace(financial_weight=0.9)


def test_unknown_yaml_keys_are_rejected(tmp_path):
    path = tmp_path / "model.yaml"
    path.write_text(yaml.safe_dump({"not_a_real_knob": 1}))
    with pytest.raises(ValueError, match="unknown config keys"):
        load_config(path)


def test_missing_config_file_falls_back_to_defaults(tmp_path):
    assert load_config(tmp_path / "absent.yaml") == ModelConfig()
