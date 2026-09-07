"""Static HTML report builder.

Produces a single self-contained page — charts inlined as base64 PNGs — so the
analysis can be committed, emailed, or served from GitHub Pages without running
anything.  The Streamlit app in ``dashboard/`` is the interactive counterpart.
"""

from __future__ import annotations

import base64
import datetime as dt
import html
from pathlib import Path

import pandas as pd

from titlei import viz
from titlei.pipeline import PipelineResult

CHART_TITLES = {
    "score_by_need_group": "Average Regents score by need tier",
    "funding_by_need_group": "Average funding per student by need tier",
    "strategy_comparison": "Proposed model vs financial-need-only baseline",
    "budget_sweep": "Sensitivity to the discretionary budget",
    "funding_vs_score": "Funding per student vs Regents score",
    "award_tiers": "Where the optimizer lands on each school",
    "top_school_scores": "Largest projected score gains",
    "top_school_funding": "Largest proportional funding increases",
}

CHART_NOTES = {
    "score_by_need_group": (
        "High-need schools absorb the per-pupil cap of $5,000 and gain the full "
        "modelled improvement; lower-need schools gain what is left."
    ),
    "strategy_comparison": (
        "The baseline ranks schools on financial need alone. The proposed model "
        "blends financial and academic need, moving dollars toward schools that "
        "are both poor and behind."
    ),
    "budget_sweep": (
        "Both strategies saturate once every eligible school reaches its cap, so "
        "the marginal value of extra budget falls away at the top end."
    ),
    "funding_vs_score": (
        "Current per-pupil funding barely tracks Regents outcomes at all "
        "(r = -0.16, so about 2% of the variance), and the sign is negative: "
        "the schools already receiving the most per pupil are the ones scoring "
        "lowest. Spending more is not, on its own, the lever — which is the "
        "observation that motivates scoring academic need separately."
    ),
}

STYLE = """
:root {
  color-scheme: light;
  --surface: #fcfcfb;
  --card: #ffffff;
  --ink: #0b0b0b;
  --ink-2: #52514e;
  --ink-3: #84837c;
  --line: #e6e5e1;
  --accent: #2a78d6;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--surface);
  color: var(--ink);
  font: 15px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}
.wrap { max-width: 1080px; margin: 0 auto; padding: 48px 24px 80px; }
header { border-bottom: 1px solid var(--line); padding-bottom: 24px; margin-bottom: 40px; }
h1 { font-size: 30px; margin: 0 0 8px; letter-spacing: -0.02em; }
h2 { font-size: 20px; margin: 48px 0 16px; letter-spacing: -0.01em; }
.sub { color: var(--ink-3); margin: 0; font-size: 14px; }
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; }
.kpi { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 16px 18px; }
.kpi .label { font-size: 12px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--ink-3); }
.kpi .value { font-size: 26px; font-weight: 600; margin-top: 6px; letter-spacing: -0.02em; }
.kpi .foot { font-size: 12px; color: var(--ink-2); margin-top: 4px; }
figure { margin: 0 0 36px; background: var(--card); border: 1px solid var(--line);
         border-radius: 10px; padding: 18px; }
figure img { width: 100%; height: auto; display: block; }
figcaption { font-size: 13px; color: var(--ink-2); margin-top: 12px; }
.tablewrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 10px; background: var(--card); }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th, td { padding: 9px 14px; text-align: right; white-space: nowrap; border-bottom: 1px solid var(--line); }
th:first-child, td:first-child { text-align: left; }
thead th { color: var(--ink-2); font-weight: 600; background: #f6f5f2; }
tbody tr:last-child td { border-bottom: none; }
.params { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }
.pill { font-size: 12px; border: 1px solid var(--line); border-radius: 999px;
        padding: 4px 12px; color: var(--ink-2); background: var(--card); }
footer { margin-top: 56px; padding-top: 20px; border-top: 1px solid var(--line);
         font-size: 13px; color: var(--ink-3); }
"""


def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def _fmt_money(value: float) -> str:
    if abs(value) >= 1e9:
        return f"${value / 1e9:.2f}B"
    if abs(value) >= 1e6:
        return f"${value / 1e6:.0f}M"
    return f"${value:,.0f}"


def _kpi(label: str, value: str, foot: str = "") -> str:
    foot_html = f'<div class="foot">{html.escape(foot)}</div>' if foot else ""
    return (
        f'<div class="kpi"><div class="label">{html.escape(label)}</div>'
        f'<div class="value">{html.escape(value)}</div>{foot_html}</div>'
    )


def _table(frame: pd.DataFrame, floats: str = "{:,.2f}") -> str:
    formatted = frame.copy()
    for column in formatted.columns:
        if pd.api.types.is_float_dtype(formatted[column]):
            formatted[column] = formatted[column].map(
                lambda v: "" if pd.isna(v) else floats.format(v)
            )
        elif pd.api.types.is_integer_dtype(formatted[column]):
            formatted[column] = formatted[column].map("{:,}".format)
    return f'<div class="tablewrap">{formatted.to_html(index=False, border=0)}</div>'


def build_report(
    result: PipelineResult,
    outdir: str | Path = "outputs",
    *,
    filename: str = "report.html",
) -> Path:
    """Render charts, tables and KPIs into one standalone HTML file."""
    outdir = Path(outdir)
    charts_dir = outdir / "charts"
    chart_paths = viz.save_all(
        combined=result.combined,
        summary=result.group_summary,
        comparison=result.comparison,
        sweep=result.sweep,
        outdir=charts_dir,
        config=result.config,
    )
    result.write_tables(outdir / "tables")

    h = result.headline
    config = result.config
    kpis = "".join(
        [
            _kpi("Budget allocated", _fmt_money(h["budget_allocated"]),
                 f"of {_fmt_money(h['budget'])} available"),
            _kpi("Schools funded", f"{int(h['schools_funded']):,}",
                 f"of {int(h['schools_modelled']):,} eligible"),
            _kpi("Students reached", f"{int(h['students_reached']):,}"),
            _kpi("Mean projected gain", f"+{h['mean_score_change']:.2f} pts",
                 f"{h['mean_score_before']:.1f} → {h['mean_score_after']:.1f}"),
            _kpi("Need-tier score gap", f"{h['gap_after']:.2f} pts",
                 f"down from {h['gap_before']:.2f} before"),
            _kpi("Funding Gini", f"{h['gini_funding_after']:.3f}",
                 f"from {h['gini_funding_before']:.3f} before"),
        ]
    )

    pills = "".join(
        f'<span class="pill">{html.escape(text)}</span>'
        for text in [
            f"{config.financial_weight:.0%} financial / {config.academic_weight:.0%} academic",
            f"FRPL floor {config.min_frpl_pct:.0f}%",
            f"High-need cap ${config.high_need_cap_per_pupil:,.0f}/pupil",
            f"Lower-need cap ${config.low_need_cap_per_pupil:,.0f}/pupil",
            f"Floor award ${config.floor_award:,.0f} below {config.floor_score:.0f} pts",
            f"Impact factor {config.impact_factor}",
        ]
    )

    figures = []
    for slug, path in chart_paths.items():
        note = CHART_NOTES.get(slug, "")
        note_html = f"<figcaption>{html.escape(note)}</figcaption>" if note else ""
        figures.append(
            f"<h2>{html.escape(CHART_TITLES.get(slug, slug))}</h2>"
            f'<figure><img alt="{html.escape(CHART_TITLES.get(slug, slug))}" '
            f'src="data:image/png;base64,{_b64(path)}">{note_html}</figure>'
        )

    sweep_table = (
        f"<h2>Budget sensitivity</h2>{_table(result.sweep)}"
        if not result.sweep.empty
        else ""
    )
    borough_table = (
        f"<h2>Allocation by borough</h2>{_table(result.borough_summary)}"
        if not result.borough_summary.empty
        else ""
    )

    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NYC Title I Funding Allocation</title>
<style>{STYLE}</style></head>
<body><div class="wrap">
<header>
  <h1>Optimized allocation of discretionary funding for NYC Title I schools</h1>
  <p class="sub">Generated {dt.date.today():%B %-d, %Y} &middot; {result.load_report.summary()}</p>
  <div class="params">{pills}</div>
</header>

<h2>Headline results</h2>
<div class="kpis">{kpis}</div>

<h2>Need tiers at a glance</h2>
{_table(result.group_summary)}

{"".join(figures)}
{sweep_table}
{borough_table}

<footer>
  Projected scores come from a linear impact assumption, not an estimated
  elasticity: every extra dollar per pupil is modelled as
  {config.impact_factor} Regents points. Treat the direction and relative
  ordering as the finding, not the absolute point gains.
</footer>
</div></body></html>
"""

    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / filename
    path.write_text(document, encoding="utf-8")
    return path
