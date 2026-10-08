# Compare conditions

"Did the compound shrink the nuclei?" is a statistics question, and the cells are not independent samples. Cells in one well share a dish, a pipetting step and a field of view. lumen-napari treats **wells as the replicates**, not cells.

## Ask

> Which compounds change nuclear area compared to DMSO?

> Compare intensity_mean_tubulin across compound against DMSO, with a dose-response on dose_um

You need a table with one row per object, a condition column (such as `compound`) and a replicate column (usually `well`). [Segmenting a folder with a plate map](plates.md) gives you one.

## What it computes

1. **Per replicate.** Objects are summarised by the **median** of each well, so a well with 500 cells does not outweigh a well with 20.
2. **Per condition**, over the well medians:

| Column | Meaning |
|---|---|
| `replicates` | Number of wells |
| `objects` | Total objects in those wells |
| `mean_<measurement>` | Mean of the well medians |
| `sd_<measurement>` | Standard deviation of the well medians |
| `fold_change` | Mean divided by the control mean |
| `z_score` | (mean − control mean) / control standard deviation |
| `p_value` | Welch's t-test (unequal variances) against the control wells |

Rows are sorted by `z_score`. The result is stored as a new table, `<table>_vs_<control>`, so you can chart or query it.

3. **Dose-response**, with a dose column: a four-parameter logistic fit of well medians against dose, per condition, giving `bottom`, `top`, `ec50` and `hill`, and `doses` (the number of distinct positive doses).

## Reading the answer

The chat posts one plain sentence per condition:

```text
- taxol: fold change 2.00, z = 14.8, p = 0.0021 (2 replicates).
- nocodazole: only 1 replicate, no test possible.
- compound_x: fold change 1.00; no test possible because the replicates do not vary.
```

The statistics are left empty (`NaN`) rather than invented when they cannot be computed:

- **One replicate:** no spread, no test.
- **Replicates that do not vary** (identical well medians in both groups): a t-test would be meaningless.
- **Control wells that do not vary:** the z-score is undefined.
- **Dose-response** needs at least four distinct positive doses and a fit that converges.

## Why not a plain average?

A mean over all cells counts every cell as a replicate. With hundreds of cells per well, almost any difference becomes "significant", and one crowded well dominates its condition. Summarising each well first, then testing across wells, answers the question the experiment can support.

Plain SQL is still there for everything else:

> Plot the median nuclear area per well, colored by compound

## Reproduce it

The comparison is recorded in the exported script:

```python
from lumen_napari.stats import compare, dose_response

result = compare(objects, "area_um2", "compound", "DMSO", replicate="well")
curves = dose_response(objects, "area_um2", "compound", "dose_um")
```
