"""Optimized allocation of discretionary funding across NYC Title I high schools.

The package turns a school-level funding and outcomes table into a linear
program that distributes a fixed discretionary budget, then scores the result
against the financial-need-only baseline the DOE uses today.
"""

from titlei.config import ModelConfig, load_config
from titlei.pipeline import PipelineResult, run_pipeline

__version__ = "1.0.0"

__all__ = ["ModelConfig", "load_config", "PipelineResult", "run_pipeline"]
