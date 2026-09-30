# Project overview

What this program does, what changed to make it a program, and what it is
useful for.

For the model's mathematics and its assumptions, see
[`methodology.md`](methodology.md). For how to run it, see the
[README](../README.md).

---

## 1. What it is

A decision-support tool for allocating a fixed pot of discretionary school
funding across NYC Title I high schools.

It answers one question: **given $X of extra money, which schools should get
it, and what would that buy?** It answers it twice — once the way the NYC DOE
allocates today (financial need alone) and once the way this project proposes
(financial *and* academic need) — and then lets you compare the two, or any
number of other policies you want to test.

The underlying analysis began as an ORIE 4820 capstone. This repository is that
analysis rebuilt as software: the same model, reproduced to the last decimal,
but now parameterised, tested, and runnable by someone who was not in the room
when it was written.

---

## 2. What changed

### 2.1 From submission to software

The submission was seven files: a workbook, two scripts and two Power BI
reports carried the analysis; an executive summary and a recorded presentation
described it. None of the five analysis files could be re-run.

| Original | Problem | Now |
|---|---|---|
| `ORIE4820_Capstone.xlsx` | Results frozen in cells; formulas not inspectable | `data/raw/nyc_title1_schools.csv` + code that regenerates every number |
| `naive_optimization.py` | Only the *baseline* model; the proposed optimiser was never in the submission | `needs.py` + `optimizer.py` implement both, reconstructed from the workbook |
| `comparison.py` | One chart, hardcoded paths, constants inline | `viz.py` — eight charts on a shared theme, driven by config |
| Two `.pbix` files | Power BI Desktop is Windows-only; binary, so not diffable and not runnable in CI | `dashboard/app.py` (Streamlit) + a standalone HTML report |

Cross-cutting, the constants were scattered across the scripts, so changing a
budget meant editing code in several places. They now live in one file,
`config/model.yaml`.

**The proposed optimiser had to be reverse-engineered.** The submission shipped
only the naive baseline script; the main combined-need model existed solely as
computed columns in the spreadsheet. It was recovered from those columns as:

```
weight = clip(0.30 · z(FRPL share) + 0.70 · (−z(Regents score)), min = 0.10)
```

and verified against the published per-school allocations at **max absolute
difference 0.0**. That check is not a one-off — it lives in
`tests/test_regression.py` and runs on every commit, so the published analysis
cannot silently drift.

### 2.2 Release history

**v1.0.0 — the rebuild**

- Eleven-module package — `config`, `data`, `needs`, `optimizer`, `simulate`,
  `metrics`, `theme`, `viz`, `report`, `pipeline`, `cli` — exposing a `titlei`
  command
- Every parameter moved into `config/model.yaml`, overridable per run
- Both strategies — proposed and baseline — implemented against one LP
- Budget sensitivity sweep (new; the original analysed $500M only)
- Standalone HTML report, Streamlit dashboard, golden regression suite, CI

**v1.1.0 — provenance, comparison, and the questionnaire**

This release exists because a tool that can run any scenario creates two new
problems: telling runs apart, and comparing them honestly.

- **Run registry** (`runs.py`). Every run writes the full parameter set that
  produced it, plus a content hash of those parameters, a timestamp and a
  label. One run is the **control**; comparisons report deltas against it.
- **Scenario comparison** (`compare.py`). Overlay any set of runs, rank them,
  and write five comparison charts.
- **Questionnaire** (`wizard.py`). `titlei wizard` asks one question per
  parameter — each explaining what it does and what moving it changes —
  validates the answer, and saves a reproducible scenario.
- **ROI and targeting metrics** (`metrics.py`), including a
  scenario-independent equity measure. See §6 for why that was necessary.
- **Saved runs tab** in the dashboard: save the current scenario, then compare.

**v1.1.0 patch — CLI flag placement**

`-v` was accepted only *before* the subcommand, so `titlei report --out outputs
-v` — the form used by CI and by `make run` / `make report` — failed. Fixed by
sharing a verbosity parent across every subparser, with regression tests
asserting both placements work and that every subcommand inherits it.

**v1.2.0 — onboarding**

Everything above assumed the reader already knew Python packaging. This release
removes that assumption.

- **`scripts/setup.sh` and `scripts/setup.ps1`** (`make setup`) build a `.venv`,
  install the package with its extras, and verify the result — on POSIX and on
  Windows. Both are safe to re-run.
- **`titlei verify`** runs nine independent checks, from Python version through
  to whether this install reproduces the published per-school allocations. It
  prints a remedy per failure and exits non-zero, so it doubles as a CI step.
  It is the answer to "does this work on my machine" for someone who will never
  run `pytest`.
- **`titlei demo`** is a narrated two-second walkthrough: it runs both
  strategies, compares them, and writes a report, naming the equivalent command
  at each step so it doubles as a tour of the CLI.
- **`python -m titlei`** works without activating the environment — the form for
  scripts and CI.
- **`titlei run --replace`** lets a caller that owns a label replace its own
  earlier runs instead of duplicating them.
- **`docs/getting-started.md`** covers the virtual environment itself: what it
  is, activation on three shells, and the fact that activation is per-terminal.

Seven bugs surfaced while building and verifying it, all pre-existing except
the last:

| Bug | Consequence |
|---|---|
| `build_report()` assumed a populated budget sweep | Raised `KeyError` on any result built with `with_sweep=False` |
| Makefile targets after `sweep` were not `.PHONY` | `make runs` silently did nothing once a `runs/` directory existed |
| Bare `titlei compare` did not bound its series count | Raised an unhandled `ValueError` past eight runs, breaking `make scenarios` |
| `titlei demo` and `make scenarios` reused labels | A second run made the label ambiguous, breaking the `titlei show` the demo itself suggests |
| Tests wrote to the repository's own `runs/` | Every `make test` quietly appended to the developer's registry |
| `titlei run` printed aggregate ROI | Displayed the metric that is identically `1000 x impact_factor` — the exact misreading §6 warns against |
| `setup.ps1` misused PowerShell's `-f` operator | Would have failed on its first step |

The last three are worth noting as a pattern: each was found not by reading the
code but by *running the documented commands verbatim* — including running them
a second and third time, which is what exposed the label collisions.

---

## 3. What the program can do

### Model and scenarios

- Score school need as a configurable blend of **financial need** (FRPL share)
  and **academic need** (inverted Regents score)
- Allocate a fixed budget by linear program, subject to per-pupil caps that
  differ by need tier and a guaranteed floor award for the lowest-scoring
  schools
- Run the **financial-need-only baseline** through the identical program, so
  the two policies differ only in how need is defined
- Project outcomes under a stated impact assumption, and sweep across budgets
  to show where the model saturates
- Refuse infeasible scenarios explicitly (`InfeasibleAllocation`) rather than
  returning a misleading answer

Twelve parameters are exposed: eligibility floor, the two need weights, the
weight floor, budget, both per-pupil caps, the floor award and its trigger
score, the impact factor, the score ceiling, and the sweep range.

### Provenance

- Every run is stored under `runs/<date>-<time>-<hash>/` with its manifest,
  per-school allocations for both strategies, group summary and sweep
- The hash fingerprints the *parameters*, so repeat runs are visible and
  differing runs cannot collide
- `titlei show <ref>` prints every parameter behind any result; refs resolve by
  id, id prefix, parameter hash, or label

### Comparison

- `titlei compare` overlays runs, ranks them on a chosen metric, and reports
  deltas against the control
- Nine ranking metrics, covering equity (gap closed, per $100M), targeting
  (share of budget and of gains reaching high-need schools), and reach
  (students per $1M)
- Five comparison charts: projected-score curves overlaid, gain by need tier, a
  targeting ranking, the equity/targeting trade-off, and budget-sensitivity
  curves
- Refuses to compare more runs than the colour palette can distinguish, rather
  than recycling hues

### Getting in

- One-command setup on POSIX and Windows, building an isolated `.venv` that
  leaves the system Python untouched
- A self-check that proves the install reproduces the published analysis, for
  someone who will never run a test suite
- A narrated walkthrough that needs no arguments and no prior knowledge
- Runnable with or without activating the environment

### Outputs and interfaces

- **CLI** — ten commands: `run`, `report`, `sweep`, `describe`, `wizard`,
  `verify`, `demo`, `runs`, `show`, `compare`
- **Static HTML report** — every chart inlined, no server, no network
- **Streamlit dashboard** — move the budget and weights and watch the
  allocation change; save scenarios and compare them in-app
- **CSV tables** for every result, so nothing is locked inside a chart
- Eight single-run charts and five comparison charts, all on one theme

### Engineering

184 tests at 97% coverage, ruff-clean, CI on Python 3.9–3.12. CI runs the
suite, the self-check, the guided demo and the full pipeline end to end, then
uploads the report as an artifact — so the onboarding path is covered by the
same gate as the model.

---

## 4. What it accomplishes

Concrete outcomes, each verifiable from the repository.

**It makes the original analysis auditable.** The capstone's results lived in
spreadsheet cells, and its main optimiser was never shipped — only the baseline
script was. The model was reconstructed from the workbook's computed columns and
now reproduces every published per-school allocation at **max absolute
difference 0.0**, checked on every commit. Anyone can confirm the numbers follow
from the stated parameters.

**It turns one frozen answer into any number of answers.** The original analysed
a single scenario — $500M at a 30/70 need index. Every parameter is now a
config field, a CLI flag and a dashboard control, and a full scenario runs in
about a second. Twenty scenarios remain readable months later because each run
stores the parameter set that produced it.

**It quantifies the capstone's central claim on a yardstick that cannot move.**
Per $100M spent, the status-quo financial-need-only rule closes the
top-vs-bottom-quartile Regents gap by **0.20 points**; the proposed 30/70 model
by **0.70** — about **3.4x better targeting on the same money**. Measured
between baseline score quartiles, which no scenario's weights can shift.

**It states the trade-off instead of burying it.** High-need schools receive
**55% of the budget while serving 26% of the students**, and the Gini
coefficient of per-pupil funding *rises* from **0.099 to 0.110**. The model
redistributes on purpose; the numbers say so plainly.

**It found two things the single-scenario analysis could not.** Aggregate return
per dollar is mathematically invariant to allocation, so no allocation is more
"efficient" than another under this impact model — only better targeted. And the
need-tier gap is redefined by each scenario's own weights, which *inverts* the
apparent ranking. Both are now enforced in code and printed as warnings. See §6.

**It located the saturation point.** Past roughly **$509M** every school hits its
per-pupil cap and further budget buys nothing. That is a finding about the caps,
not the money, and it is invisible if you only ever run one budget.

**It made the work runnable by a stranger.** One command builds an isolated
environment; a second proves the install reproduces the published results; a
third produces a full report. No database, no API keys, no network.

---

## 5. What it is useful for

**Testing a funding policy before defending it.** The core use. Set the
parameters that describe a policy, run it, and get the allocation, the
projected outcomes, and the distributional consequences. Change one parameter
and see what moves.

**Making the equity trade-off explicit rather than implicit.** The model does
not hide that it redistributes. It reports the share of budget going to
high-need schools (55% of the money for 26% of students), and the Gini
coefficient of per-pupil funding *rising* from 0.099 to 0.110. Anyone arguing
about the policy can see the trade-off in numbers instead of adjectives.

**Comparing policies on a fixed yardstick.** The reason the run registry and
the scenario-independent metrics exist. Five plausible policies produce five
plausible-sounding results; without a control and a stable measure, the
comparison is noise.

**Reproducing and auditing the original capstone.** The golden regression means
anyone can verify this code produces the submitted numbers, and see exactly
which parameters produced them.

**Teaching or demonstrating constrained optimisation.** A small, real,
well-documented LP with genuine policy stakes, a questionnaire front-end, and
an honest account of what its assumptions do and do not support.

### Who it is for

- **Analysts** testing allocation rules against a stated objective
- **Decision-makers** who need the trade-off stated in students and dollars
- **Reviewers** checking that a result follows from its stated parameters
- **Students** wanting a worked, tested example of an optimisation model with
  its assumptions written down

---

## 6. Two findings that shape how results should be read

Building the comparison tooling surfaced two ways this model can quietly
mislead. Both are handled in code and printed as warnings by `titlei compare`.
Neither is obvious from the original analysis, which only ever ran one
scenario.

### Aggregate return is invariant to allocation

A school's gain is `funding / enrollment × k`, so the student-points it
receives are `enrollment × funding / enrollment × k = funding × k`. Summed
across schools, that is `budget × k`.

**Total return depends only on how much you spend, never on where you spend
it.** Every allocation, however well or badly targeted, returns exactly the
same aggregate. Any "return per dollar" ranking is therefore vacuous — the
first version of that metric read exactly `1,000.000` for all five test
scenarios.

The consequence for the analysis: in this model, "which allocation is better"
is **never** an efficiency question. It is only ever a distributional one. The
scorecard excludes the invariant metric and ranks on targeting instead;
`tests/test_compare.py` asserts the identity directly, so if the impact model
ever stops being linear, the tests will say so.

### The need-tier gap moves its own goalposts

`gap_closed` measures the Regents gap between high-need and lower-need schools.
But each scenario defines those tiers from its *own* weights, so comparing that
gap across differently-weighted scenarios compares differently-composed groups.

This is not a technicality. Ranked on the scenario-defined tier gap,
financial-need-only appears to **beat** the proposed model. That ordering is an
artifact of the groups moving.

`academic_gap_closed` instead uses the top and bottom quartile of *baseline*
Regents scores — groups no scenario can change. On that fixed yardstick the
capstone's central claim holds cleanly: per $100M spent, financial-need-only
closes the gap by **0.20 points**, the proposed 30/70 model by **0.70** —
roughly 3.4× better targeting on the same money. This is the default ranking
metric.

---

## 7. What it cannot do

Stated plainly, because a tool that produces confident-looking numbers should
be explicit about their limits.

- **It does not estimate the effect of money on outcomes.** `impact_factor =
  0.001` is an assumption carried from the original study, not a fitted
  coefficient. It implies no diminishing returns, no lag, and identical
  responsiveness at every school. Read the comparison between strategies, not
  the absolute point gains.
- **It has no counterfactual.** Every school is observed at one funding level,
  so there is no variation from which to identify a causal effect.
- **It is one year, cross-sectional.** Nothing here speaks to trends.
- **It does not reallocate base funding** — only the discretionary pot.
- **It treats Regents averages as academic need**, inheriting every critique of
  standardised testing as a measure of school quality.
- **It has no geographic balance constraint.** Brooklyn and the Bronx absorb
  59% of the budget; that is an output, not a design goal.

---

## 8. Command reference

| Command | Does |
|---|---|
| `titlei verify` | Check this install works and reproduces the published results |
| `titlei demo` | Guided end-to-end walkthrough; no arguments needed |
| `titlei describe` | Summarise the input data and what the eligibility filter drops |
| `titlei run` | Run both strategies, write CSVs, register the run |
| `titlei report` | Run and build the standalone HTML report |
| `titlei sweep` | Compare strategies across a range of budgets |
| `titlei wizard` | Build a scenario by answering questions, then run it |
| `titlei runs` | List saved runs with their parameters side by side |
| `titlei show <ref>` | Every parameter and result behind one run |
| `titlei compare` | Overlay runs, rank them, write comparison charts |

Useful `make` targets: `setup` (start here), `verify`, `demo`, `test`, `lint`,
`report`, `scenarios` (register five standard scenarios and compare them),
`dashboard`.

Setup, on either platform:

| | |
|---|---|
| macOS / Linux | `./scripts/setup.sh`, then `source .venv/bin/activate` |
| Windows | `.\scripts\setup.ps1`, then `.\.venv\Scripts\Activate.ps1` |
| Without activating | `.venv/bin/python -m titlei <command>` |
