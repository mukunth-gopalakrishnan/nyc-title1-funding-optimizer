# Getting started

Ten minutes from a fresh clone to your own scenario. No prior knowledge of the
project, and none of Python packaging.

---

## 1. Set up (one command)

```bash
./scripts/setup.sh
```

That creates a virtual environment in `.venv`, installs everything, and checks
the result. It is safe to re-run. Then activate it:

```bash
source .venv/bin/activate
```

<details>
<summary>Prefer to do it by hand?</summary>

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,dashboard]"
```

</details>

**Requirements:** Python 3.9 or newer. Nothing else — no database, no API keys,
no network access. The school data is committed to the repository.

---

## 2. Check that it works

```bash
titlei verify
```

```
  [PASS] Python version                     3.12.1
  [PASS] Dependencies                       all 5 importable
  [PASS] Configuration                      $500M budget, 30%/70% need index
  [PASS] School data                        349 of 349 schools retained
  [PASS] Need scoring                       171 high-need, 178 lower-need
  [PASS] Allocation solves                  $500,000,000 across 335 schools
  [PASS] Outcome projection                 mean +3.15 Regents points
  [PASS] Reproduces published results       max difference $0.00e+00
  [PASS] Output directory                   outputs is writable
```

The check that matters most is the eighth: it re-runs the model and compares
every school's allocation against the numbers published in the original
capstone. If it passes, your install is producing the real analysis, not an
approximation.

Any failure prints what to do about it. `titlei verify` exits non-zero on
failure, so it works in a script or a CI step.

---

## 3. See it work

```bash
titlei demo
```

A narrated walkthrough, about two seconds. It loads the data, runs the proposed
model, runs the status-quo baseline against it, compares the two, and writes a
report — naming the equivalent command at each step, so it doubles as a tour of
the CLI.

Open what it produced:

```bash
open outputs/demo/report.html
```

---

## 4. Run your own scenario

The guided way — one question per parameter, each explaining what it does:

```bash
titlei wizard
```

The direct way, if you already know what you want to change:

```bash
titlei run --budget 750e6 --label "Three quarters of a billion"
```

Useful flags: `--budget`, `--financial-weight`, `--high-need-cap`,
`--low-need-cap`, `--min-frpl-pct`, `--impact-factor`. Full list:
`titlei run --help`.

---

## 5. Compare scenarios

Every run is saved with the exact parameters that produced it, so you can come
back to a folder of twenty runs and still tell them apart.

```bash
titlei runs                    # list them, parameters side by side
titlei show "Half budget"      # everything behind one run
titlei compare                 # overlay them all, ranked
```

`titlei compare` writes five charts to `outputs/comparison/`, including the
projected-score curves of every scenario laid over each other.

**Two warnings it prints, and why they matter.** Aggregate return per dollar is
mathematically identical for every allocation in this model, so ranking on it
ranks nothing. And the "need-tier gap" is defined by each scenario's own
weights, so it is not comparable across scenarios that weight need differently.
The default ranking metric avoids both traps. See
[methodology §4a](methodology.md) if you want the derivation.

---

## 6. The interactive dashboard

```bash
streamlit run dashboard/app.py
```

Move the budget and the need weights with sliders and watch the allocation
change. The **Saved runs** tab saves the current scenario and compares it
against the others.

---

## Try changing something

A good first experiment, because the answer is not obvious:

```bash
titlei run --low-need-cap 5000 --label "Equal caps"
titlei compare
```

That removes the tier distinction in the per-pupil cap — an equal-treatment
policy. Does it close the outcome gap more or less than the targeted one? The
comparison will tell you, and the answer depends on which yardstick you rank on.

---

## Where things live

| Path | What |
|---|---|
| `config/model.yaml` | Every parameter, with comments |
| `data/raw/` | The school data (349 Title I high schools) |
| `outputs/` | Charts, tables and the HTML report |
| `runs/` | Saved runs, one directory each |
| `src/titlei/` | The model |
| `docs/overview.md` | What the project does and what it is for |
| `docs/methodology.md` | The model written out, and its limits |

---

## If something breaks

| Symptom | Fix |
|---|---|
| `command not found: titlei` | Activate the environment: `source .venv/bin/activate` |
| `ModuleNotFoundError` | `pip install -e ".[dev,dashboard]"` |
| `school data not found` | Run from the repository root; see `data/README.md` |
| `InfeasibleAllocation` | The guaranteed floor awards exceed your budget — raise `--budget` or lower `floor_award` |
| Anything else | `titlei verify` names the stage that broke |

Developers: `make test` runs the full suite, `make lint` checks style.
