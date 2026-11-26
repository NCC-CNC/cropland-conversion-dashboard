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

- Which region definition: ecoregions, ecodistricts, joint venture areas?
- Is a province-wide view (no region chosen) expected?
