# Tiled cell data for province scale

## Status

Accepted (2026-11-26, owner decision on regions and tiles; tile size chosen
from measurement).

## Context

The web app loads one `cells.json` per area and sums cells inside a drawn
polygon (ADR 0002). Manitoba and Saskatchewan coverage (issue #28) is up to
about 1.3 million 1 km cells, far too large for one file. The owner decided
that users choose among 14 farming-zone ecoregion regions
(`web/public/data/regions.json`) while fixed tiles do the loading, so a shape
that crosses a region edge still works. See
`docs/design/05_regional_partitioning.md`.

## Decision

Add an optional tiled form of an area, `contract_version` 3:

- Tiles are 100 km squares in EPSG:3978 with edges at multiples of 100 000 m
  from the projection origin, so they are aligned to the 1 km grid and line up
  across areas and runs. A cell belongs to the tile holding its centre, so it is
  in exactly one tile. The tile size is a pipeline option (`--tiled KM`).
- One file per non-empty tile, `web/public/data/<area_id>/tiles/<col>_<row>.json`
  (signed integers, row increases northward), with the same columnar shape as
  `cells.json` plus a `region` column.
- One `web/public/data/<area_id>/index.json` lists tiles with a WGS84 bbox, cell
  count, byte size and the regions each tile touches, plus per-region cell
  counts, tile lists and pre-summed totals.
- A non-tiled area (no `index.json`, `meta.tiled` absent) keeps working as
  today. `meta.json` of a tiled area has `contract_version` 3, `tiled: true`
  and `tile_km`, and has no `cells.json`.

Why 100 km: on the SK/MB test area a full 100 km tile is about 1.8 MB raw
(about 0.2 MB gzipped, what Pages serves) and the median is 0.75 MB, so the
sizing target of about 1 MB raw per tile (median) holds and a province needs
about 150 to 200 files. 50 km tiles have the same total download but four
times as many files (median 0.33 MB), so more requests and a bigger index for
no real gain at this density. Both sizes are measured in the design note.

## Consequences

- A polygon fetches only the tiles whose bbox it intersects; a region pick
  fetches the tiles listed for that region.
- Summing logic is reusable: each tile is a valid `cells.json` for its cells.
  Summing all tiles reproduces the single file exactly (checked by test and on
  real data).
- Region membership is by cell centre and the source layers are coarse, so edge
  cells are approximate; `region` is -1 for cells in no region.
- The web loader and a province summary are separate work (build list 17, 18).
  Until the web app reads `index.json`, tiled areas must not be published.
- Tile size is fixed per dataset; changing it rewrites every tile.
