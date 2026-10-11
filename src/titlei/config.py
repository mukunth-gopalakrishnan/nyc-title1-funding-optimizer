"""Configuration for the allocation model.

Every knob the capstone model exposes lives here so that a scenario is fully
described by a config object rather than by edits scattered through scripts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from titlei.resources import CONFIG_FILE

DEFAULT_CONFIG_PATH = CONFIG_FILE


@dataclass(frozen=True)
class ModelConfig:
    """Parameters of one allocation scenario."""

    # --- eligibility -----------------------------------------------------
    min_frpl_pct: float = 60.0
    """Title I eligibility floor, as a percentage of K-12 enrollment on FRPL."""

    # --- need index ------------------------------------------------------
    financial_weight: float = 0.30
    """Share of the combined need score driven by financial need (FRPL)."""

    academic_weight: float = 0.70
    """Share driven by academic need (inverted Regents z-score)."""

    weight_floor: float = 0.10
    """Lower clip on the need score; schools at the floor are 'lower-need'."""

    # --- budget and caps -------------------------------------------------
    extra_budget: float = 500_000_000.0
    """Discretionary dollars to distribute on top of existing funding."""

    high_need_cap_per_pupil: float = 5_000.0
    low_need_cap_per_pupil: float = 1_500.0

    floor_score: float = 60.0
    """Schools below this Regents average are guaranteed a minimum award."""

    floor_award: float = 50_000.0
    """The guaranteed minimum award for schools below ``floor_score``."""

    # --- outcome model ---------------------------------------------------
    impact_factor: float = 0.001
    """Regents points gained per extra dollar of per-pupil funding."""

    max_score: float = 100.0
    """Regents scores are capped here after applying the impact model."""

    # --- scenario sweep --------------------------------------------------
    sweep_budgets: tuple[float, ...] = (
        100_000_000.0,
        250_000_000.0,
        500_000_000.0,
        750_000_000.0,
        1_000_000_000.0,
    )

    def __post_init__(self) -> None:
        total = self.financial_weight + self.academic_weight
        if abs(total - 1.0) > 1e-9:
            raise ValueError(
                f"financial_weight + academic_weight must sum to 1.0, got {total}"
            )
        if self.low_need_cap_per_pupil > self.high_need_cap_per_pupil:
            raise ValueError("low-need cap cannot exceed the high-need cap")
        for name in ("extra_budget", "impact_factor", "weight_floor"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")

    def replace(self, **changes: Any) -> ModelConfig:
        """Return a copy of this config with ``changes`` applied."""
        return ModelConfig(**{**asdict(self), **changes})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_config(path: str | Path | None = None) -> ModelConfig:
    """Load a :class:`ModelConfig` from YAML, falling back to the defaults."""
    path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not path.exists():
        return ModelConfig()

    with path.open(encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    if "sweep_budgets" in payload and payload["sweep_budgets"] is not None:
        payload["sweep_budgets"] = tuple(float(b) for b in payload["sweep_budgets"])

    known = {f for f in ModelConfig.__dataclass_fields__}
    unknown = set(payload) - known
    if unknown:
        raise ValueError(f"unknown config keys in {path}: {sorted(unknown)}")

    return ModelConfig(**payload)
