# Methodology

How the allocation model is built, why each choice was made, and what the
results do not support.

## 1. Population and eligibility

The frame is NYC public **high schools designated Title I** with at least 60% of
K-12 enrollment on free or reduced-price lunch (FRPL). After dropping schools
missing any model field or reporting zero enrollment, 349 schools remain,
covering 210,396 students.

The 60% floor is a policy threshold, not a statistical one. Lowering it via
`min_frpl_pct` widens the pool and dilutes the per-school award.

## 2. Defining need

Two quantities are standardised across the eligible pool:

| Term | Definition | Reads as |
|---|---|---|
| `FRPL_Z` | z-score of FRPL count ÷ enrollment | financial need |
| `Score_Z` | **negated** z-score of the average Regents score | academic need |

The negation is the crux. A school one standard deviation *below* the mean
Regents average scores `Score_Z = +1` — it needs more, not less.

```
Weight = clip(0.30 · FRPL_Z + 0.70 · Score_Z, min = 0.10)
```

**Why 30/70?** It encodes the study's position that academic need is the
under-served signal, since financial need is already the sole basis of the
status quo. It is a policy weight, not a fitted parameter. The dashboard slider
and `--financial-weight` exist so a reader can disagree with it and see what
changes.

**Why clip at 0.10?** Two jobs. It keeps every objective coefficient positive,
so the LP never prefers *withholding* money from a school. And it defines the
tier boundary: a school still sitting at the floor after the blend is
"lower-need" (178 schools); anything above is "high-need" (171).

Both z-scores use the sample standard deviation (`ddof=1`), matching the
original spreadsheet.

## 3. The allocation program

```
maximise    Σᵢ wᵢ · xᵢ
subject to  Σᵢ xᵢ  ≤  B                        (budget)
            lᵢ ≤ xᵢ ≤ capᵢ · enrollmentᵢ       (per-school bounds)
```

- `xᵢ` — extra dollars to school *i* (continuous)
- `wᵢ` — the need weight above
- `B` — $500M by default
- `capᵢ` — $5,000 per pupil for high-need schools, $1,500 otherwise
- `lᵢ` — $50,000 if the school averages below 60 on the Regents, else 0

Solved with `scipy.optimize.linprog(method="highs")`.

**Why caps at all?** Without them the LP is degenerate: it hands the entire
budget to the single highest-weighted school. The caps convert "maximise
weighted need" into "fund by need priority until the money runs out," which is
what an allocation policy actually looks like.

**Why the floor award?** It is a political-feasibility constraint. A model that
sends literally nothing to a failing school is not adoptable, whatever its
objective value. The floor is clipped to each school's own cap so it can never
create an infeasible bound; if the floors in aggregate exceed the budget, the
optimiser raises `InfeasibleAllocation` rather than returning something
misleading.

**What the solution looks like.** Because the objective is linear and the only
coupling constraint is the budget, the LP drives nearly every school to a corner
of its box: 334 of 349 schools land exactly at their tier cap, one takes a
partial award, and 14 receive nothing. This is why `award_tiers` charts counts
rather than a distribution — there is no meaningful spread to show.

## 4. Projecting outcomes

```
projected = min(score + extra_per_pupil × 0.001, 100)
```

**This is the weakest link in the analysis and should be read as such.**

`impact_factor = 0.001` says $1,000 of extra per-pupil funding buys one Regents
point. It was chosen as a plausible round number in the original study, not
estimated from data. It implies:

- **no diminishing returns** — the ten-thousandth dollar works as hard as the first;
- **no lag** — spending converts to test scores within the year;
- **uniform responsiveness** — a school with weak staffing responds exactly like one with strong staffing;
- **no spending composition** — a dollar on tutoring and a dollar on facilities are identical.

None of these hold. The empirical literature on school spending finds effects
that are real but smaller, slower, and highly dependent on what the money buys.

**What survives the assumption.** Both strategies are scored through the *same*
function, so the comparison between them — and the ranking of schools within a
strategy — depends on the allocation, not on the constant. Halve
`impact_factor` and every projected gain halves; the ordering does not move.
What does *not* survive is any absolute claim: "+5 Regents points" is the
model's arithmetic, not a forecast.

The allocation itself is independent of `impact_factor` entirely — it appears
only after the LP has been solved.

## 5. What the data cannot tell you

**No counterfactual.** Every school is observed under one funding level. There
is no variation to identify a causal effect of money on scores, so the model
assumes one.

**Regents averages as a proxy.** Using test scores as "academic need" inherits
every critique of standardised testing — differential preparation, selection
into which exams students sit, and score distributions that are not comparable
across very different school types.

**Composition effects in the tails.** The schools with the largest *proportional*
funding increases are almost all YABC (Young Adult Borough Center) transfer
programs. These serve over-age, under-credited students, have unusual per-pupil
funding baselines, and are not comparable to comprehensive high schools. They
top that chart because their denominator is small, not because the model
identified them as the best investment.

**One year, one snapshot.** The data is cross-sectional. Nothing here speaks to
trends, and the model represents a single year of allocation with no
reallocation of base funding.

**Equity, not equality — by construction.** The Gini coefficient of per-pupil
funding rises from 0.099 to 0.110. High-need schools serve 26% of students and
receive 55% of the budget. That is the model working as designed, and it is a
value judgement, not a technical result: it holds that closing outcome gaps
justifies unequal dollar distribution. A reader who rejects that premise should
reject the allocation, and the weights are exposed so they can compute their own.

## 6. Reproducing the original analysis

`tests/test_regression.py` checks this implementation against the per-school
outputs published in the original `ORIE4820_Capstone.xlsx`:

- need scores (`FRPL_Z`, `Score_Z`, `Weight`) and tier assignment
- optimised funding and per-pupil awards, both strategies
- projected scores and score changes
- the need-tier summary table

All to within 1e-9 (1e-6 on dollar amounts). The fixtures in `tests/fixtures/`
are exports of the original workbook sheets and should be treated as immutable.

If you change a default in `config/model.yaml`, the regression tests will fail —
that is intended. They pin the *published* scenario, not whatever scenario is
currently configured.

## 7. Extending the model

Worth doing, roughly in order of value:

1. **Replace the impact model.** Even a crude regression of score changes on
   funding changes across years would beat a constant.
2. **Add a diminishing-returns term.** Concave returns turn the LP into a convex
   program (still tractable) and would stop every school pinning to its cap.
3. **Constrain by borough or district.** The current model has no geographic
   balance constraint; Brooklyn and the Bronx absorb 59% of the budget.
4. **Model spending categories.** The source data carries staffing, instruction
   and support breakdowns that the allocation currently ignores entirely.
