# Contributing

```bash
pip install -e ".[dev,dashboard]"
make test
```

## Ground rules

**The golden fixtures are immutable.** `tests/fixtures/` holds the per-school
results published in the original capstone workbook. `tests/test_regression.py`
pins this code to them. If a change makes those tests fail, the change altered
the published analysis — either revert it, or make it opt-in through
`ModelConfig` so the default scenario still reproduces.

**Defaults live in two places and must agree.** `config/model.yaml` and the
`ModelConfig` dataclass defaults are checked against each other by
`test_default_config_matches_shipped_yaml`. Change both.

**New parameters go through `ModelConfig`.** No magic numbers in
`optimizer.py`, `simulate.py` or `viz.py` — if it is tunable, it is a config
field, a CLI flag, and a dashboard control.

**Charts follow `theme.py`.** Categorical colours are assigned in fixed slot
order and never cycled; text uses ink tokens, never a series colour; any chart
with two or more series carries a legend *and* direct labels. If you need a
third series, use `SERIES_3` — past three, facet instead.

**Claims in the README carry their numbers.** If you change the model, re-run
`make report` and update any figure quoted in `README.md` or
`docs/methodology.md`.

## Layout

```
src/titlei/
  config.py      parameters, YAML loading, validation
  data.py        loading, cleaning, eligibility filtering
  needs.py       z-scores and the two need definitions
  optimizer.py   the linear program
  simulate.py    outcome projection, scenarios, budget sweep
  metrics.py     summaries, Gini, gaps, headline numbers
  theme.py       chart colours and matplotlib defaults
  viz.py         chart builders (return Figures, never save)
  report.py      static HTML report
  pipeline.py    orchestration
  cli.py         the `titlei` command
```

`viz.py` returns figures so the same chart serves both the static report and the
Streamlit app. Keep it that way.
