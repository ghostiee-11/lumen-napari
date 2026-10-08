"""Compare conditions the way a screen should be analysed: wells are the replicates, not cells."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import optimize, stats


def per_replicate(df: pd.DataFrame, measurement: str, replicate: str, condition: str,
                  dose: str | None = None) -> pd.DataFrame:
    """One row per replicate (well) with the median of its objects, so a well with many cells
    does not outweigh one with few."""
    keys = [condition, replicate] + ([dose] if dose else [])
    grouped = df.groupby(keys, dropna=False)
    out = grouped[measurement].median().rename(measurement).reset_index()
    out["objects"] = grouped.size().to_numpy()
    return out


def compare(df: pd.DataFrame, measurement: str, condition: str, control: str,
            replicate: str = "well") -> pd.DataFrame:
    """Per condition: replicates, mean and sd of replicate medians, z-score and fold change
    against the control replicates, and a Welch t-test against the control."""
    wells = per_replicate(df, measurement, replicate, condition)
    controls = wells.loc[wells[condition] == control, measurement]
    if controls.empty:
        names = sorted(map(str, wells[condition].unique()))
        raise ValueError(f"No {condition} == {control!r}. Conditions: {names}.")
    mu, sd = controls.mean(), controls.std(ddof=1)
    rows = []
    for name, group in wells.groupby(condition, dropna=False):
        values = group[measurement]
        # A t-test needs spread: with identical replicates its p-value is meaningless.
        testable = (name != control and len(values) > 1 and len(controls) > 1
                    and (values.std(ddof=1) > 0 or controls.std(ddof=1) > 0))
        test = stats.ttest_ind(values, controls, equal_var=False) if testable else None
        rows.append({
            condition: name,
            "replicates": len(values),
            "objects": int(group["objects"].sum()),
            f"mean_{measurement}": values.mean(),
            f"sd_{measurement}": values.std(ddof=1),
            "fold_change": values.mean() / mu if mu else np.nan,
            "z_score": (values.mean() - mu) / sd if sd else np.nan,
            "p_value": test.pvalue if test is not None else np.nan,
        })
    return pd.DataFrame(rows).sort_values("z_score", na_position="last").reset_index(drop=True)


def four_parameter(x, bottom, top, ec50, hill):
    return bottom + (top - bottom) / (1 + (x / ec50) ** -hill)


def dose_response(df: pd.DataFrame, measurement: str, condition: str, dose: str,
                  replicate: str = "well") -> pd.DataFrame:
    """A four-parameter logistic fit of the replicate medians against dose, per condition.
    Conditions with fewer than four positive doses, that do not converge, or that do not
    respond to dose (see `_responds`) get NaN."""
    wells = per_replicate(df, measurement, replicate, condition, dose)
    rows = []
    for name, group in wells.groupby(condition, dropna=False):
        group = group[group[dose] > 0]
        fit = {"bottom": np.nan, "top": np.nan, "ec50": np.nan, "hill": np.nan}
        if group[dose].nunique() >= 4:
            x, y = group[dose].to_numpy(float), group[measurement].to_numpy(float)
            start = [y.min(), y.max(), float(np.median(x)), 1.0]
            try:
                params, _ = optimize.curve_fit(four_parameter, x, y, p0=start, maxfev=10_000)
                if _responds(x, y, params):
                    fit = dict(zip(fit, params, strict=True))
            except (RuntimeError, ValueError):
                pass
        rows.append({condition: name, "doses": group[dose].nunique(), **fit})
    return pd.DataFrame(rows)


def _responds(x: np.ndarray, y: np.ndarray, params) -> bool:
    """Whether the fitted curve is a real response: its EC50 lies within the tested doses and,
    when there are spare points, it fits clearly better than a flat line (F-test, p < 0.05)."""
    if not x.min() <= params[2] <= x.max():
        return False
    if len(y) <= 4:
        return True
    flat = np.sum((y - y.mean()) ** 2)
    curve = np.sum((y - four_parameter(x, *params)) ** 2)
    if curve == 0:
        return flat > 0
    f = ((flat - curve) / 3) / (curve / (len(y) - 4))
    return stats.f.sf(f, 3, len(y) - 4) < 0.05
