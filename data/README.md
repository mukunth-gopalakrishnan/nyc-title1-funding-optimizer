# Data

## `raw/nyc_title1_schools.csv`

One row per NYC Title I high school (349 rows, 50 columns), assembled from NYC
DOE school-level allocation reporting and Regents outcome reporting for a single
academic year.

### Columns the model uses

| Column | Meaning |
|---|---|
| `School Name` | Join key across every table in this project |
| `Avg Regents Score` | Average Regents examination score, 0–100 |
| `K-12 Enrollment` | Total K-12 enrollment |
| `K-12 FRPL Count` | Students on free or reduced-price lunch |
| `FRPL %` | The same as a percentage; drives the eligibility filter |
| `Total School Funding per Pupil` | All sources, per pupil |

`School DBN`, `District` and `Borough` are carried through for reporting.

### Everything else

The remaining ~44 columns describe staffing (teacher experience bands,
paraprofessionals, admin, pupil support), allocation by purpose, funding by
source (state/local vs federal), community-schools spending, and Fair Student
Funding formula detail. The model does not read them; they are kept because they
are the obvious material for extending it.

### Known quirks

- **YABC schools.** Young Adult Borough Centers are transfer programs for
  over-age, under-credited students. Their per-pupil funding baselines are
  unusual and they dominate any *proportional*-change ranking. Treat them
  separately in any per-school reading.
- **Header whitespace.** A few source columns carry trailing spaces
  (`All Other `, `Federal Funding  `). The loader strips them on read.
- **Percent columns.** `FRPL %` may arrive as `91.24` or `"91.24%"`. The loader
  coerces both.
- **One year only.** Cross-sectional. No trends are inferable.

## `processed/`

Generated, git-ignored. Written by `titlei run` / `titlei report`.

## Regenerating from the source workbook

The CSV was extracted from the `final_data_new` sheet of the original
`ORIE4820_Capstone.xlsx`:

```python
import pandas as pd

raw = pd.read_excel("ORIE4820_Capstone.xlsx", "final_data_new")
raw.columns = [c.strip() for c in raw.columns]
raw = raw.loc[:, ~raw.columns.duplicated()].dropna(axis=1, how="all")
raw.to_csv("data/raw/nyc_title1_schools.csv", index=False)
```

The golden fixtures in `tests/fixtures/` come from that same workbook's
`optimized_full_results`, `naive_optimization` and
`optimized_low_high_need_scores` sheets. They pin the published results and
should not be regenerated from this code — that would defeat their purpose.
