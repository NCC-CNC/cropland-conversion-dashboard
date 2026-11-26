# 05 Manitoba and Saskatchewan coverage and partitioning

Status: proposal, with the region list and tile format decided (below).
Tracks issue #28. Requested in client feedback of 2026-11-26.

## Request

The final version should allow selection of areas with data anywhere in
Manitoba and Saskatchewan. Other regions can become separate dashboards later.
Decision (2026-11-26): combine regional choice with fixed tiles.

## Proposal: regions for choosing, tiles for loading

- A **region** is what the user picks (for example an ecoregion or a named
  study region). It sets the map extent and the default view, as `areas.json`
  does today.
- A **tile** is the unit of data loading. Cells are split into a fixed grid
  (for example 0.5 degree tiles, or an equal-area scheme chosen by the
  pipeline). Each tile is a small `cells` file with the same columnar layout.
- The browser loads only tiles that intersect the drawn shape (or the current
  view for the heat map) and sums cells across them. A shape that crosses a
  region boundary works because tiles, not regions, hold data.

### Layout

Superseded by the tile format below (ADR 0004). The first sketch used a
zoom pyramid and a per-dataset `regions.json`; neither is needed, because
regions are tagged on each cell and the ecoregion list is one shared file.
Existing single-area folders keep working.

### Web changes

- Area picker becomes a region picker that zooms the map.
- Tile loader with a cache; summary waits for all tiles under the shape.
- Heat map loads tiles for the current view only, thinned at low zoom.
- Show a progress state while tiles load and a clear message if one fails.

## Size and cost estimate (to verify)

Province-wide at 1 km is of the order of 650,000 km2 per province, so up to
about 1.3 million cells before dropping cells with no natural cover. Tiling
keeps any single download small. Measure the real total on the test area
first (issue #30) and extrapolate before committing to a tile size.

### Measured sizes (2026-11-26)

Four targets, default filters, baselines 2011, 2016 and 2021 to 2025. The
Interlake window (id `mb-interlake`, 99.9 km square, about 10,000 km2, Gimli
to Fisher Branch) was added as a forest, wetland and pasture heavy contrast to
the farmland-dense SK/MB test area. It touches the Interlake Plain (about 69
percent), Lake Manitoba Plain (16) and Mid-Boreal Lowland (14) ecoregions.

|Area|km2|Cells kept|cells.json|gzipped|MB per 1,000 km2 (raw, gz)|PMTiles|
|---|---|---|---|---|---|---|
|SK/MB test area|28,800|n/a|6.87 MB|0.68 MB|0.239, 0.024|not built|
|MB Interlake window|10,000|7,651|2.15 MB|0.24 MB|0.215, 0.024|2.16 MB|

The expectation that forest and wetland country gives a larger file per km2
did not hold: 76 percent of Interlake cells have natural cover, and per km2 the
file is slightly smaller than in the SK/MB area, because most cells have zero
conversion for the rarer targets and those arrays are sparse. The 5 MB to 10
MB raw guideline per tile therefore corresponds to roughly 20,000 to 45,000
km2 at about 0.22 to 0.24 MB per 1,000 km2, or 0.5 MB to 1.1 MB gzipped
transfer. Province-wide (about 1.3 million km2 of MB and SK farmed and
boreal land) would be roughly 300 MB raw and 30 MB gzipped before dropping
empty cells, well inside the Pages limit. These are two windows, not a
province sample; northern boreal cells with little change may be smaller.

## Hosting limits

GitHub Pages sites are limited to about 1 GB. If the tiles exceed that,
move them to a release asset or object store and keep the app on Pages. This
should be decided with measured sizes.

## Open questions

- Is a province-wide view (no region chosen) expected?

## Region definition (decided 2026-11-26)

Regions are the National Ecological Framework for Canada **ecoregions**,
farming zone only: ecozone 9 (Boreal Plains) and ecozone 10 (Prairies),
clipped to Manitoba and Saskatchewan. Pieces of one ecoregion within one
province are merged, so an ecoregion that spans the border becomes two regions.
This gives 14 regions (the sizing research counted 15 pieces; the 15th is a
5 km2 sliver of Interlake Plain in Saskatchewan caused by the coarse provincial
boundary, dropped by a 10 km2 minimum).

Built by `python -m cropconv.regions` (`pipeline/cropconv/regions.py`) and
written to `web/public/data/regions.json`, a small GeoJSON FeatureCollection
(about 73 KB) in WGS84. This is the region list for the picker; it is separate
from the per-dataset `regions.json` sketched in the layout above, which becomes
a plain list of ids once cells carry a region id.

|Property|Meaning|
|---|---|
|`id`|Stable slug of the name plus province code, for example `mixed-grassland-sk`|
|`name`|Display name (the source typo "Manotoba" is fixed by an override table)|
|`province`|`MB` or `SK`|
|`ecoregion`, `ecozone`|National Ecological Framework codes|
|`area_km2`|Clipped area before simplification, equal-area projection (Canada Albers)|

|Id|Name|Area km2|
|---|---|---|
|aspen-parkland-mb|Aspen Parkland|35,098|
|aspen-parkland-sk|Aspen Parkland|81,009|
|boreal-transition-mb|Boreal Transition|3,217|
|boreal-transition-sk|Boreal Transition|53,976|
|cypress-upland-sk|Cypress Upland|5,027|
|interlake-plain-mb|Interlake Plain|39,922|
|lake-manitoba-plain-mb|Lake Manitoba Plain|32,679|
|mid-boreal-lowland-mb|Mid-Boreal Lowland|70,951|
|mid-boreal-lowland-sk|Mid-Boreal Lowland|21,066|
|mid-boreal-uplands-mb|Mid-Boreal Uplands|12,029|
|mid-boreal-uplands-sk|Mid-Boreal Uplands|101,996|
|mixed-grassland-sk|Mixed Grassland|86,494|
|moist-mixed-grassland-sk|Moist Mixed Grassland|67,923|
|southwest-manitoba-uplands-mb|Southwest Manitoba Uplands|2,180|

### Sources and processing

- Ecoregions: AAFC `ecoregion_shp.zip` (Open Government Licence - Canada),
  downloaded from `sis.agr.gc.ca`. The layer is the 2003 product at 1:1 000 000
  in NAD83 (CSRS) geographic coordinates.
- Province boundary: Natural Earth 10m admin-1 (public domain). Statistics
  Canada boundary files were not usable here (the download returns 403 to
  scripts) and the AAFC province layer URL failed, so Natural Earth was used.
  It is accurate enough for the straight MB and SK borders at this scale.
- Both are reprojected to EPSG:3978 (edges densified first), intersected,
  merged, simplified at 1 km, and written in WGS84 with 4 decimals.
- Downloads are cached in `pipeline/cache/` (never committed), extracted flat
  into their own directories and read only with pyshp, shapely and pyproj.

### Use

`assign_regions(lon, lat)` returns a region id per cell centroid (None outside
every region) and `region_areas_km2()` returns the area per region.

Caveat: the ecoregion source is coarse (1:1M, 2003) and the provincial
boundary is coarse, so cell assignment near region edges is approximate, and a
small share of cells near the edge of the farming zone or a province border may
have no region. Do not present region edges as exact.

## Tile format (decided 2026-11-26, build item 16)

Decision record: `docs/decisions/0004-tiled-cell-data.md`. Built by
`python -m cropconv.run --area <id> --tiled [KM]` (`pipeline/cropconv/tiling.py`),
which writes tiles and `index.json` instead of `cells.json`. Contract version 3.

```text
web/public/data/<area_id>/
  meta.json              as before, plus contract_version 3, tiled true, tile_km
  index.json             tiles, regions and region totals
  tiles/<col>_<row>.json one file per non-empty tile, for example tiles/-6_1.json
```

- **Tile grid**: 100 km squares in EPSG:3978, edges at multiples of 100 000 m,
  so tiles are aligned to the 1 km grid. `col = floor(x / 100000)` and
  `row = floor(y / 100000)` of the cell centre (row grows northward, both can
  be negative). A cell is in exactly one tile. The option takes another size in
  km; a dataset must use one size.
- **Tile file**: the `cells.json` shape (`lon`, `lat`, `area_ha`, `intervals` with
  nested `converted_ha` by target), plus `region`, an integer per cell that
  indexes `index.json` `regions` (-1 for a cell in no region). Readers that
  ignore `region` sum tiles exactly as they sum `cells.json`.
- **index.json**: tile `bbox` is the WGS84 extent of the tile's cells (not the
  full square), for intersection tests. Tile `regions` maps the region ids
  present in the tile to cell counts. `region_summary` lists regions with cells
  in this area, the tiles to fetch to cover a picked region, and pre-summed
  totals per interval, target and class (a province summary can reuse them).
  `unassigned` has the cell count, and totals, for cells in no region.
  `regions` lists every ecoregion id in sorted order, so a tile's `region`
  integers mean the same in every area.

```json
{
  "area_id": "sk-mb-estevan-melville",
  "contract_version": 3,
  "crs": "EPSG:3978",
  "tile_m": 100000,
  "cell_size_m": 1000,
  "cells": 21652,
  "regions": ["aspen-parkland-mb", "aspen-parkland-sk", "..."],
  "region_summary": [
    {"id": "aspen-parkland-sk", "name": "Aspen Parkland", "cells": 16041, "area_ha": 1600000.0,
     "tiles": ["-6_0", "-6_1"],
     "totals": {"2016-2025": {"natural_ha": {"forest": 0.0}, "converted_ha": {"crop": {"forest": 0.0}}}}}
  ],
  "unassigned": {"cells": 0},
  "tiles": [
    {"id": "-6_1", "col": -6, "row": 1, "file": "tiles/-6_1.json",
     "bbox": [-103.2531, 49.5708, -101.9581, 50.5542], "cells": 6475, "bytes": 1799430,
     "regions": {"aspen-parkland-sk": 6348, "moist-mixed-grassland-sk": 127}}
  ]
}
```

Values in the example are shortened. `totals` has the targets and classes
that the area's `cells.json` arrays would have, so a class can sum to zero in
one region.

### A non-tiled area

An area with no `index.json` (and no `tiled` in `meta.json`) is read from
`cells.json` as today, at contract version 1 or 2. A reader should treat
`meta.tiled` as the switch.

### Measured on the SK/MB test area (21,652 cells, all four targets)

The single `cells.json` is 5.98 MB raw (about 280 bytes per cell). Summing all
tiles reproduces it exactly for every array, so every target, class and
interval (`math.fsum` on the real run, and a unit test on a synthetic grid).

|Tile size|Tiles|Raw median|Raw max|Gzip median|Gzip total|
|---|---|---|---|---|---|
|100 km (chosen)|6|753 KB|1,799 KB|76 KB|0.57 MB|
|50 km|16|326 KB|628 KB|30 KB|0.59 MB|

The test area is a rectangle, so its edge tiles are partial; a full 100 km
tile at this density is about 1.8 MB raw, so the 1 MB median target holds only
where tiles are partial or sparser. Gzipped (what Pages serves) a full tile is
about 0.2 MB. `index.json` is 7 KB for 6 tiles, about 0.3 KB per tile. All
cells fell inside a region on this area. Extrapolating about 1.3 million cells
at 280 bytes gives about 360 MB raw and under 50 MB gzipped, well under the
1 GB Pages limit.

### What the web loader and province summary need

- Read `meta.json`; if `tiled`, fetch `index.json` once, otherwise `cells.json`.
- For a drawn polygon, fetch tiles whose `bbox` intersects its bounding box and
  sum cells with centre inside the polygon, as today. For a picked region, use
  `region_summary[].tiles` and keep cells whose `region` index matches.
- A province summary can add `region_summary[].totals` over the regions of a
  province (the id ends in `-mb` or `-sk`) without loading tiles. Cells in no
  region are in `unassigned` only.
