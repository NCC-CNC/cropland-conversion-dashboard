# 05 Manitoba and Saskatchewan coverage and partitioning

Status: proposal. Tracks issue #28. Requested in client feedback of 2026-11-26.

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

```text
web/public/data/<dataset_id>/
  meta.json              dataset description, snapshots, targets, tile scheme
  regions.json           [{id, name, bbox}]
  tiles/<z>/<x>_<y>.json one cells file per tile that has any data
  tiles/index.json       list of existing tiles, so empty ones are never fetched
```

`areas.json` becomes `regions.json` within a dataset. Existing single-area
folders keep working until migrated.

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

| Property | Meaning |
| --- | --- |
| `id` | Stable slug of the name plus province code, for example `mixed-grassland-sk` |
| `name` | Display name (the source typo "Manotoba" is fixed by an override table) |
| `province` | `MB` or `SK` |
| `ecoregion`, `ecozone` | National Ecological Framework codes |
| `area_km2` | Clipped area before simplification, equal-area projection (Canada Albers) |

| Id | Name | Area km2 |
| --- | --- | --- |
| aspen-parkland-mb | Aspen Parkland | 35,098 |
| aspen-parkland-sk | Aspen Parkland | 81,009 |
| boreal-transition-mb | Boreal Transition | 3,217 |
| boreal-transition-sk | Boreal Transition | 53,976 |
| cypress-upland-sk | Cypress Upland | 5,027 |
| interlake-plain-mb | Interlake Plain | 39,922 |
| lake-manitoba-plain-mb | Lake Manitoba Plain | 32,679 |
| mid-boreal-lowland-mb | Mid-Boreal Lowland | 70,951 |
| mid-boreal-lowland-sk | Mid-Boreal Lowland | 21,066 |
| mid-boreal-uplands-mb | Mid-Boreal Uplands | 12,029 |
| mid-boreal-uplands-sk | Mid-Boreal Uplands | 101,996 |
| mixed-grassland-sk | Mixed Grassland | 86,494 |
| moist-mixed-grassland-sk | Moist Mixed Grassland | 67,923 |
| southwest-manitoba-uplands-mb | Southwest Manitoba Uplands | 2,180 |

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
