import numpy as np
import pandas as pd
import pytest
from lumen.pipeline import Pipeline
from lumen.sources.duckdb import DuckDBSource
from napari.components import ViewerModel
from skimage.io import imsave

from lumen_napari.batch import measure_files
from lumen_napari.plate import PlateHeatmap, per_well, plate_for, plate_shape


def test_plate_shape():
    assert plate_shape(pd.Series(["A01", "H12"])) == ("ABCDEFGH", 12)
    assert plate_shape(pd.Series(["A01", "B13"]))[1] == 24
    assert plate_shape(pd.Series(["P01"]))[0][-1] == "P"


def test_per_well():
    df = pd.DataFrame({"well": ["A01", "A01", "B03"], "area": [1.0, 3.0, 5.0]})
    wells = per_well(df, "area")
    assert wells.to_dict("list") == {
        "column": [1, 3], "row": ["A", "B"], "mean area": [2.0, 5.0], "well": ["A01", "B03"],
    }
    assert list(per_well(df, "area", "count")["objects"]) == [2, 1]


@pytest.fixture
def plate_table(tmp_path):
    for well, n in (("A01", 1), ("B02", 2)):
        image = np.zeros((20, 50), np.uint8)
        for i in range(n):
            image[5:12, 5 + 20 * i:12 + 20 * i] = 200
        imsave(tmp_path / f"p_{well}.png", image, check_contrast=False)
    df = measure_files(sorted(tmp_path.glob("*.png")), min_size=0)
    source = DuckDBSource.from_df(tables={"plate": df})
    source.tables["plate"] = "SELECT * FROM plate"
    return Pipeline(source=source, table="plate")


async def test_applies_to_well_tables(plate_table):
    assert await PlateHeatmap.applies(plate_table)


def test_click_a_well_opens_its_image(qapp, plate_table):
    viewer = ViewerModel()
    heatmap = plate_for(viewer).instance(statistic="count")
    heatmap(plate_table, {})
    assert list(heatmap._wells["objects"]) == [1, 2]
    heatmap._selection.event(index=[1])
    assert [layer.name for layer in viewer.layers] == ["p_B02", "p_B02 labels"]
    assert heatmap._dynamic_provides == {"selected_well": "B02"}


def test_heatmap_renders(qapp, plate_table):
    import holoviews as hv

    pane = plate_for(ViewerModel()).instance()(plate_table, {})
    plot = hv.render(pane.object)
    assert plot.title.text.startswith("mean area per well")
