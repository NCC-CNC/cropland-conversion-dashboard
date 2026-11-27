# Shapefile verification

Check that the per-year ACI shapefile zips for the SK/MB test area (release
`test-area-shapefiles-v1`, made by `python -m cropconv.export_shapes`) hold the
same class areas as the raster they were made from.

## Method

For each year 2009 to 2025 (all 17):

1. Read the zip in memory with pyshp. For every polygon, take the signed ring
   area (outer rings clockwise, holes counter-clockwise, as the exporter writes
   them) and add it to the total for that polygon's `CODE`. Result: area per
   ACI class code in km2.
2. Read the cached raster
   `~/cropconv-cache/aci_<year>_3978_-581160_50490_-434820_247350_30m.tif`
   (the test-area bbox) and count pixels per class code, excluding 0 (no data).
   Area is count times the cell area taken from the raster itself.
3. Compare every class present in either source. A class is flagged if it
   differs by more than 0.1 km2 or more than 0.1 percent.

## Result

All 17 years pass. Every class matches to floating point rounding
(largest absolute difference 9e-13 km2, largest relative difference
2e-14 percent). No class was flagged and no class was present in only one source.

| Year | Classes checked | Max abs diff (km2) | Max rel diff (%) | Result |
| ---- | --------------- | ------------------ | ---------------- | ------ |
| 2009 | 30 | 4e-16 | 1e-14 | pass |
| 2010 | 34 | 9e-13 | 2e-14 | pass |
| 2011 | 26 | 5e-13 | 2e-14 | pass |
| 2012 | 30 | 1e-13 | 1e-14 | pass |
| 2013 | 36 | 9e-13 | 2e-14 | pass |
| 2014 | 36 | 9e-13 | 2e-14 | pass |
| 2015 | 31 | 2e-13 | 2e-14 | pass |
| 2016 | 31 | 1e-13 | 2e-14 | pass |
| 2017 | 34 | 1e-13 | 2e-14 | pass |
| 2018 | 37 | 9e-13 | 2e-14 | pass |
| 2019 | 38 | 9e-13 | 2e-14 | pass |
| 2020 | 38 | 9e-13 | 2e-14 | pass |
| 2021 | 37 | 9e-13 | 2e-14 | pass |
| 2022 | 33 | 1e-13 | 2e-14 | pass |
| 2023 | 37 | 1e-14 | 2e-14 | pass |
| 2024 | 38 | 1e-13 | 2e-14 | pass |
| 2025 | 38 | 9e-13 | 2e-14 | pass |

The per-class table behind this (raster km2, shapefile km2, difference) is
reproducible with the method above; it was kept in scratch, not in the repo.

## Caveats

- Both sides come from the same cached raster. This proves the vectorising and
  zipping step loses nothing (no dropped patches, no hole or ring errors). It
  does not test the fetch from AAFC or the accuracy of the ACI itself. The
  earlier 2024 check against the source raster covers the fetch for that year.
- The cached 2009 and 2010 rasters are 30 m grids (cell size read from the
  raster as 30 m), not the native 56 m. Those two years were resampled to 30 m
  when fetched, so their shapefile patches follow 30 m cells.
- Areas are planar areas in EPSG:3978 (Lambert conformal conic), the same
  projection as the raster, so no reprojection error enters the comparison.
- Class areas include every ACI code present, including water, urban and
  other non-natural classes, not only the dashboard groups.
