# Getting started

Ten minutes from a fresh clone to your own scenario. No prior knowledge of the
project, and none of Python packaging.

---

## 0. Just want to try it?

You don't need Python. Download the single-file program for your computer from
the repository's **Releases** page, double-click it, and it runs the guided demo
and opens the report. The README's *Download and run* section covers the
one-time security prompt on first launch.

Everything below is for working with the source.

---

## 1. Set up (one command)

**macOS / Linux**

```bash
./scripts/setup.sh
```

**Windows (PowerShell)**

```powershell
.\scripts\setup.ps1
```

Either one creates a virtual environment in `.venv`, installs everything, and
verifies the result. Both are safe to re-run.

<details>
<summary>Prefer to do it by hand?</summary>

```bash
python3 -m venv .venv                 # Windows: python -m venv .venv
source .venv/bin/activate             # Windows: .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip   # needed: editable installs want pip >= 21.3
pip install -e ".[dev,dashboard]"
```

That pip upgrade is not optional on a stock macOS Python 3.9, which ships pip
21.2 — without it the install fails with a misleading "setup.py not found".
`scripts/setup.sh` and `scripts/setup.ps1` already do this for you.

</details>

**Requirements:** Python 3.9 or newer. Nothing else — no database, no API keys,
no network access. The school data is committed to the repository.

> The Windows script mirrors the shell one step for step, but it has been
> reviewed rather than executed on Windows — this project is developed on
> macOS. If it misbehaves, the manual steps above always work.

---

## 1a. Working in the virtual environment

The `.venv` directory is a self-contained box holding its own Python and its
own copy of every dependency, plus the `titlei` command itself. Nothing is
installed system-wide, and deleting `.venv` removes every trace.

**Activate it** — this puts `.venv`'s programs first on your `PATH`, so typing
`titlei` finds the one in the box:

| | |
|---|---|
| macOS / Linux | `source .venv/bin/activate` |
| Windows (PowerShell) | `.\.venv\Scripts\Activate.ps1` |
| Windows (cmd.exe) | `.venv\Scripts\activate.bat` |

Your prompt gains a `(.venv)` prefix. That prefix is how you know you are
inside the box.

**Check you are in it:**

```bash
which titlei          # Windows: where titlei
```

It should print a path inside `.venv`. If it prints nothing, you are not
activated.

**Leave it:**

```bash
deactivate
```

**Activation is per-terminal and does not persist.** Every new terminal window
starts outside the box, so run the activate command again. You do not re-run
setup — the environment is still there, you are just not in it.

**Or skip activation entirely.** The venv's own Python can run the tool
directly, from any directory, without touching your `PATH`:

```bash
.venv/bin/python -m titlei verify      # Windows: .venv\Scripts\python -m titlei verify
```

That is the form to use in a script, a cron job, or a CI step, where activation
is awkward.

> **`command not found: titlei`** is almost always a missing activation in a
> new terminal. Run the activate command for your platform and try again.

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
| `command not found: titlei` | You are not in the venv. Activate it (§1a), or use `.venv/bin/python -m titlei ...` |
| `.ps1 cannot be loaded` (Windows) | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then re-run |
| `permission denied: ./scripts/setup.sh` | `bash scripts/setup.sh` |
| `ModuleNotFoundError` | `pip install -e ".[dev,dashboard]"` |
| `school data not found` | Run from the repository root; see `data/README.md` |
| `InfeasibleAllocation` | The guaranteed floor awards exceed your budget — raise `--budget` or lower `floor_award` |
| Anything else | `titlei verify` names the stage that broke |

Developers: `make test` runs the full suite, `make lint` checks style.
