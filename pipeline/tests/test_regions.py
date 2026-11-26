import os

import numpy as np
import pytest
from shapely.geometry import box, mapping

from cropconv import regions as rg


def fc(*feats):
    return {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"id": i, "area_km2": a}, "geometry": mapping(g)} for i, g, a in feats
        ],
    }


def test_slug_and_id():
    assert rg.slugify("Mixed Grassland") == "mixed-grassland"
    assert rg.slugify("Chaîne d'Ellesmere (N)") == "chaine-d-ellesmere-n"
    assert rg.region_id("Moist Mixed Grassland  ", "SK") == "moist-mixed-grassland-sk"


def test_name_override_fixes_source_typo():
    assert rg.display_name("Southwest Manotoba Uplands ") == "Southwest Manitoba Uplands"
    assert rg.region_id("Southwest Manotoba Uplands", "MB") == "southwest-manitoba-uplands-mb"
    assert rg.display_name("Aspen Parkland") == "Aspen Parkland"


def test_clip_merges_pieces_and_splits_by_province():
    prov = {"SK": box(0, 0, 100_000, 100_000), "MB": box(100_000, 0, 200_000, 100_000)}
    eco = [
        {"ecoregion": 1, "ecozone": 10, "source_name": "Aspen Parkland", "geom": box(50_000, 0, 150_000, 40_000)},
        {"ecoregion": 1, "ecozone": 10, "source_name": "Aspen Parkland", "geom": box(60_000, 60_000, 90_000, 90_000)},
        {"ecoregion": 2, "ecozone": 9, "source_name": "Outside", "geom": box(500_000, 0, 600_000, 10_000)},
    ]
    out = rg.clip_regions(eco, prov)
    assert [r["id"] for r in out] == ["aspen-parkland-mb", "aspen-parkland-sk"]
    by = {r["id"]: r for r in out}
    assert by["aspen-parkland-mb"]["geom"].area == pytest.approx(50_000 * 40_000)
    assert by["aspen-parkland-sk"]["geom"].area == pytest.approx(50_000 * 40_000 + 30_000 * 30_000)


def test_clip_drops_slivers():
    prov = {"SK": box(0, 0, 100_000, 100_000)}
    eco = [{"ecoregion": 1, "ecozone": 10, "source_name": "Sliver", "geom": box(99_000, 0, 100_500, 2_000)}]
    assert rg.clip_regions(eco, prov) == []  # 3 km2


def test_assign_regions_vectorised_and_none_outside():
    regions = fc(("a-sk", box(-110, 49, -105, 53), 1.0), ("b-mb", box(-105, 49, -100, 53), 1.0))
    lon = np.array([-108.0, -102.0, -120.0, -105.5])
    lat = np.array([50.0, 50.0, 50.0, 60.0])
    got = rg.assign_regions(lon, lat, regions)
    assert list(got) == ["a-sk", "b-mb", None, None]
    grid = rg.assign_regions(lon.reshape(2, 2), lat.reshape(2, 2), regions)
    assert grid.shape == (2, 2) and grid[0, 0] == "a-sk"


def test_region_areas_from_properties():
    regions = fc(("a-sk", box(0, 0, 1, 1), 12.5))
    assert rg.region_areas_km2(regions) == {"a-sk": 12.5}


def test_feature_collection_roundtrip_wgs84():
    r = [
        {
            "id": "x-sk",
            "name": "X",
            "ecoregion": 1,
            "ecozone": 10,
            "province": "SK",
            "geom": rg._reproject(box(-108, 50, -107, 51), "EPSG:4326", rg.WORK_CRS),
        }
    ]
    out = rg.to_feature_collection(r, simplify_m=100.0)
    p = out["features"][0]["properties"]
    assert p["id"] == "x-sk"
    assert 7000 < p["area_km2"] < 8500  # about 1 x 1.1 degrees at 50 N
    assert rg.assign_regions([-107.5], [50.5], out)[0] == "x-sk"


@pytest.mark.skipif(not os.environ.get("CROPCONV_NETWORK_TESTS"), reason="set CROPCONV_NETWORK_TESTS=1 to download sources")
def test_build_from_real_sources():
    built = rg.build()
    ids = {f["properties"]["id"] for f in built["features"]}
    assert "mixed-grassland-sk" in ids and "southwest-manitoba-uplands-mb" in ids
    assert 10 <= len(ids) <= 20
