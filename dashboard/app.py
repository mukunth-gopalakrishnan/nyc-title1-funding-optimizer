"""Interactive allocation dashboard — the Python replacement for the Power BI report.

Run with::

    streamlit run dashboard/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:  # allow running without installing the package
    sys.path.insert(0, str(ROOT / "src"))

from titlei import metrics, viz  # noqa: E402
from titlei.config import load_config  # noqa: E402
from titlei.data import FUNDING_PER_PUPIL, SCHOOL, SCORE, load_schools  # noqa: E402
from titlei.needs import NEED_GROUP  # noqa: E402
from titlei.simulate import (  # noqa: E402
    CHANGE,
    EXTRA_PER_PUPIL,
    FUNDING_AFTER,
    PERCENT_INCREASE,
    PROJECTED,
    compare_strategies,
    run_scenario,
    sweep_budgets,
)

st.set_page_config(
    page_title="NYC Title I Funding Allocation",
    page_icon="🎓",
    layout="wide",
)


@st.cache_data(show_spinner=False)
def _load(data_path: str | None):
    config = load_config(ROOT / "config" / "model.yaml")
    schools, report = load_schools(data_path, config)
    return schools, report, config


@st.cache_data(show_spinner=False)
def _scenario(_schools: pd.DataFrame, _config, strategy: str, budget: float):
    frame, allocation = run_scenario(
        _schools, _config, strategy=strategy, budget=budget
    )
    return frame, allocation.budget_used, allocation.schools_funded


@st.cache_data(show_spinner=False)
def _sweep(_schools: pd.DataFrame, _config, budgets: tuple[float, ...]):
    return sweep_budgets(_schools, _config, budgets)


schools, load_report, base_config = _load(None)

st.title("Optimized allocation of discretionary funding")
st.caption(
    "NYC Title I high schools · " + load_report.summary()
)

with st.sidebar:
    st.header("Scenario")
    budget = st.slider(
        "Discretionary budget",
        min_value=50,
        max_value=1500,
        value=int(base_config.extra_budget / 1e6),
        step=50,
        format="$%dM",
    ) * 1e6
    financial = st.slider(
        "Weight on financial need",
        min_value=0.0,
        max_value=1.0,
        value=base_config.financial_weight,
        step=0.05,
        help="The remainder goes to academic need (inverted Regents score).",
    )
    high_cap = st.number_input(
        "High-need cap ($ per pupil)",
        min_value=0,
        max_value=20_000,
        value=int(base_config.high_need_cap_per_pupil),
        step=250,
    )
    low_cap = st.number_input(
        "Lower-need cap ($ per pupil)",
        min_value=0,
        max_value=20_000,
        value=int(base_config.low_need_cap_per_pupil),
        step=250,
    )
    impact = st.number_input(
        "Impact factor (points per $/pupil)",
        min_value=0.0001,
        max_value=0.01,
        value=float(base_config.impact_factor),
        step=0.0005,
        format="%.4f",
    )
    st.divider()
    st.caption(
        "Projected scores rest on a linear impact assumption, not an estimated "
        "elasticity. Read the direction, not the decimals."
    )

config = base_config.replace(
    financial_weight=financial,
    academic_weight=1.0 - financial,
    high_need_cap_per_pupil=float(high_cap),
    low_need_cap_per_pupil=float(max(low_cap, 0)),
    impact_factor=float(impact),
    extra_budget=float(budget),
)

try:
    combined, used, funded = _scenario(schools, config, "combined", budget)
    naive, _, _ = _scenario(schools, config, "naive", budget)
except Exception as exc:  # infeasible caps/budget combinations
    st.error(f"This scenario has no feasible allocation: {exc}")
    st.stop()

summary = metrics.group_summary(combined)
comparison = compare_strategies(combined, naive)
headline = metrics.headline_metrics(combined, budget)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Budget allocated", f"${used / 1e6:,.0f}M", f"{used / budget:.0%} of budget")
c2.metric("Schools funded", f"{funded:,}", f"of {len(combined):,} eligible")
c3.metric("Students reached", f"{int(headline['students_reached']):,}")
c4.metric(
    "Mean projected gain",
    f"+{headline['mean_score_change']:.2f} pts",
    f"{headline['mean_score_before']:.1f} → {headline['mean_score_after']:.1f}",
)
c5.metric(
    "Need-tier score gap",
    f"{headline['gap_after']:.2f} pts",
    f"{headline['gap_after'] - headline['gap_before']:+.2f} vs before",
    delta_color="inverse",
)

overview, strategy, schools_tab, sensitivity, data_tab = st.tabs(
    ["Before & after", "Strategy comparison", "Schools", "Budget sensitivity", "Data"]
)

with overview:
    left, right = st.columns(2)
    left.pyplot(viz.score_by_need_group(summary))
    right.pyplot(viz.funding_by_need_group(summary))
    st.pyplot(viz.funding_vs_score_scatter(combined))
    st.pyplot(viz.award_tiers(combined, config))
    st.dataframe(summary, width="stretch")

with strategy:
    st.pyplot(viz.strategy_comparison(comparison))
    st.markdown(
        "The baseline ranks schools on financial need alone — the DOE's current "
        "practice. The proposed model blends financial and academic need, so a "
        "school that is both poor and behind outranks one that is only poor."
    )
    delta = (
        comparison.groupby(NEED_GROUP)[
            ["Score Change Naive", "Score Change Combined"]
        ]
        .mean()
        .assign(Difference=lambda d: d["Score Change Combined"] - d["Score Change Naive"])
    )
    st.dataframe(delta, width="stretch")

with schools_tab:
    groups = st.multiselect(
        "Need tier",
        options=sorted(combined[NEED_GROUP].unique()),
        default=sorted(combined[NEED_GROUP].unique()),
    )
    view = combined[combined[NEED_GROUP].isin(groups)]
    if "Borough" in combined.columns:
        boroughs = st.multiselect(
            "Borough",
            options=sorted(combined["Borough"].dropna().unique()),
            default=sorted(combined["Borough"].dropna().unique()),
        )
        view = view[view["Borough"].isin(boroughs)]

    if view.empty:
        st.info("No schools match the current filters.")
    else:
        left, right = st.columns(2)
        left.pyplot(viz.top_school_scores(view))
        right.pyplot(viz.top_school_funding(view))
        columns = [
            SCHOOL, NEED_GROUP, SCORE, PROJECTED, CHANGE,
            FUNDING_PER_PUPIL, EXTRA_PER_PUPIL, FUNDING_AFTER, PERCENT_INCREASE,
        ]
        if "Borough" in view.columns:
            columns.insert(1, "Borough")
        st.dataframe(
            view[columns].sort_values(CHANGE, ascending=False),
            width="stretch",
            hide_index=True,
        )
        st.download_button(
            "Download this view (CSV)",
            view[columns].to_csv(index=False).encode("utf-8"),
            file_name="allocation.csv",
            mime="text/csv",
        )

with sensitivity:
    sweep = _sweep(schools, config, tuple(config.sweep_budgets))
    st.pyplot(viz.budget_sweep(sweep))
    st.pyplot(viz.budget_sweep(sweep, "High-Need Mean Score Change"))
    st.dataframe(sweep, width="stretch", hide_index=True)

with data_tab:
    st.subheader("Model inputs")
    st.dataframe(schools, width="stretch", hide_index=True)
    st.subheader("Active parameters")
    st.json(config.to_dict())
