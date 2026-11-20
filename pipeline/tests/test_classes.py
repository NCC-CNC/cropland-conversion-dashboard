import numpy as np
import pytest

from cropconv import classes as cl


@pytest.fixture(scope="module")
def luts():
    return cl.build_luts()


def group_of(luts, code):
    return cl.GROUPS[luts[0][code]]


def natural_of(luts, code):
    i = luts[1][code]
    return cl.NATURAL_CLASSES[i - 1] if i else None


@pytest.mark.parametrize(
    "code,cls",
    [(50, "shrubland"), (80, "wetland"), (110, "grassland"), (200, "forest"),
     (210, "forest"), (220, "forest"), (230, "forest")],
)
def test_natural_codes(luts, code, cls):
    assert group_of(luts, code) == "natural"
    assert natural_of(luts, code) == cls


@pytest.mark.parametrize("code", [120, 121, 130, 131, 133, 146, 153, 162, 199])
def test_crop_codes(luts, code):
    assert group_of(luts, code) == "crop"
    assert natural_of(luts, code) is None


def test_pasture_is_separate_group(luts):
    assert group_of(luts, 122) == "pasture"


@pytest.mark.parametrize("code", [10, 20, 30, 34, 35, 60, 85])
def test_other_codes(luts, code):
    assert group_of(luts, code) == "other"


def test_unknown_and_nodata_map_to_other(luts):
    assert group_of(luts, 0) == "other"
    assert group_of(luts, 255) == "other"


def test_csv_is_consistent():
    rows = cl.load_classes()
    codes = [r["code"] for r in rows]
    assert codes == sorted(codes)
    assert 110 in codes and 230 in codes
    # every natural class in the contract is reachable
    assert {r["natural_class"] for r in rows if r["natural_class"]} == set(cl.NATURAL_CLASSES)
    # no em dashes anywhere in the mapping file
    text = cl.CLASSES_CSV.read_text(encoding="utf-8")
    assert chr(0x2014) not in text


def test_unknown_codes():
    arr = np.array([0, 10, 110, 250], dtype=np.uint8)
    assert cl.unknown_codes(arr) == [250]


def test_legend_label_check():
    rows = cl.load_classes()
    good = [r["label"] for r in sorted(rows, key=lambda r: r["code"])]
    assert cl.check_legend_labels(good) == []
    assert cl.check_legend_labels(good[:-1])  # missing label reported
    assert cl.check_legend_labels(good + ["Brand new class"])
    swapped = list(good)
    swapped[0], swapped[1] = swapped[1], swapped[0]
    assert cl.check_legend_labels(swapped)  # order change reported
