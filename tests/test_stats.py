import numpy as np
import pandas as pd
import pytest

from lumen_napari.stats import compare, dose_response, four_parameter, per_replicate


def screen():
    """Two DMSO wells and two taxol wells. One taxol well has many cells, which must not
    outweigh the other."""
    rows = []
    for well, compound, n, area in (("A01", "DMSO", 10, 100), ("A02", "DMSO", 10, 110),
                                    ("B01", "taxol", 200, 200), ("B02", "taxol", 5, 220)):
        rows += [{"well": well, "compound": compound, "area": area}] * n
    return pd.DataFrame(rows)


def test_wells_are_the_replicates():
    wells = per_replicate(screen(), "area", "well", "compound")
    assert wells.objects.tolist() == [10, 10, 200, 5]
    assert wells.area.tolist() == [100, 110, 200, 220]


def test_compare_against_control():
    result = compare(screen(), "area", "compound", "DMSO").set_index("compound")
    assert result.loc["taxol", "replicates"] == 2
    assert result.loc["taxol", "mean_area"] == 210  # the mean of wells, not of 205 cells
    assert result.loc["taxol", "fold_change"] == pytest.approx(210 / 105)
    assert result.loc["taxol", "z_score"] == pytest.approx((210 - 105) / np.std([100, 110], ddof=1))
    assert result.loc["taxol", "p_value"] < 0.05
    assert np.isnan(result.loc["DMSO", "p_value"])


def test_missing_control_lists_conditions():
    with pytest.raises(ValueError, match="Conditions: \\['DMSO', 'taxol'\\]"):
        compare(screen(), "area", "compound", "PBS")


def test_dose_response_recovers_the_ec50():
    doses = [0.01, 0.1, 0.3, 1, 3, 10, 100]
    rows = [{"well": f"W{i}", "compound": "x", "dose": d, "area": four_parameter(d, 50, 150, 1.0, 1.5)}
            for i, d in enumerate(doses)]
    rows += [{"well": "C1", "compound": "y", "dose": 1, "area": 1.0}]
    fit = dose_response(pd.DataFrame(rows), "area", "compound", "dose").set_index("compound")
    assert fit.loc["x", "ec50"] == pytest.approx(1.0, rel=1e-3)
    assert fit.loc["x", "doses"] == 7
    assert np.isnan(fit.loc["y", "ec50"])


def test_identical_replicates_give_no_p_value():
    df = pd.DataFrame({"well": ["A1", "A2", "B1", "B2"], "compound": ["DMSO", "DMSO", "x", "x"],
                       "area": [100, 100, 200, 200]})
    row = compare(df, "area", "compound", "DMSO").set_index("compound").loc["x"]
    assert np.isnan(row.p_value) and np.isnan(row.z_score)
    assert row.fold_change == 2


def test_flat_response_gets_no_ec50():
    rng = np.random.default_rng(0)
    doses = [0.01, 0.1, 1, 10]
    rows = [{"well": f"W{i}{r}", "compound": "inert", "dose": d, "area": 35 + rng.normal(0, 1)}
            for i, d in enumerate(doses) for r in range(2)]
    fit = dose_response(pd.DataFrame(rows), "area", "compound", "dose").iloc[0]
    assert np.isnan(fit.ec50) and np.isnan(fit.bottom)
