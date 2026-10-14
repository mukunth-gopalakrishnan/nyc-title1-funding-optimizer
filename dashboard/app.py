"""Kept so that ``streamlit run dashboard/app.py`` still works.

The dashboard itself lives in the package, at ``src/titlei/_dashboard/app.py``,
so that every install has it. The easier way to start it is::

    titlei dashboard
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:  # allow running without installing the package
    sys.path.insert(0, str(SRC))

from titlei.resources import DASHBOARD_APP  # noqa: E402

# run_path, not import: Streamlit re-executes this file on every interaction,
# and an import would run the app only the first time.
runpy.run_path(str(DASHBOARD_APP), run_name="__main__")
