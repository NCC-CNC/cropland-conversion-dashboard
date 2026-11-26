# Session Handoff: 2026-11-26

## Summary

Client feedback on the MVP was triaged into issues #25 to #31. Two web features
shipped and are live, three design documents were written, and the raw
per-year shapefiles for the v2 test area were built and staged as a draft
GitHub Release. The client liked the dashboard and asked that caveats, data
source and methods stay in a very similar format.

## Completed

- Issues opened: #25 to #31 (one per feedback item).
- #32: selection coordinates panel (with copy) and a Markdown methods and
  results report download. Deployed to Pages.
- #33: design note `03_land_series_recommendations.md` (side task, nothing
  built).
- #34: `04_conversion_targets.md`, `05_regional_partitioning.md` and ADR
  0003 (pre-tiled 30 m layer, Proposed).
- #35: `python -m cropconv.export_shapes`, raw per-year ACI shapefiles.
- Draft GitHub Release `test-area-shapefiles-v1` with 17 zips (2009 to 2025,
  about 665 MB). Not published, no tag yet.
- Decisions from the owner today: pre-tiled 30 m layer for small selections;
  urban/developed and barren reported as separate targets (greenhouse not
  selected); regions for choosing plus tiles for loading; zips on GitHub
  Releases; every year for the test area; raw ACI class codes in shapefiles.

## Current state

- Live site has the coordinates panel and Download report button.
- Test area extent is the EPSG:3978 rectangle around Estevan, Melita,
  Russell and Melville (about 146 x 197 km, 28,800 km2), not the
  quadrilateral. It may include land outside the four towns' shape.
- Shapefile areas were checked against the raster for 2024 only (five largest
  classes match to 0.1 km2). 2009 and 2010 are 56 m in the source.
- The dashboard has not been run on the test area yet (no summaries, no
  `areas.json` entry). #30 is only partly done.
- Land Series note is unverified on per-class accuracy, legend and overlap with
  ACI: the data product specification was not retrieved.
- Open PR: #17 (dependabot, setup-python 6 to 7), CI passing, awaiting owner OK.

## Next actions

1. Publish the draft release (or review first), then close the zips part of #30.
2. Check shapefile areas against rasters for a few more years.
3. Run the dashboard pipeline on the test area and add it to `areas.json`
   (rest of #30), using the shapefiles to assess accuracy.
4. Decide the pasture and forage question (about 2x effect), then noise filter
   defaults (#3), before building #27.
5. Accept or revise ADR 0003, then build the contract change for #27 and the
   tiling for #28, then the 30 m layer (#29).
6. Verify the Land Series note against the data product specification.

## Risks or decisions needed

- Whether to merge dependabot #17.
- Wording for the lower-confidence caveat on urban and barren targets.
- Region definition for Manitoba and Saskatchewan (ecoregions, ecodistricts
  or joint venture areas) and whether a province-wide view is expected.
- Hosting size: Pages is limited to about 1 GB, so tiles may need a Release or
  object store.
- Real phone, tablet and screen reader checks are still not done.
