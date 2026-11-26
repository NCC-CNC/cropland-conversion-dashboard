# Session Handoff: 2026-11-26 (build session)

## Summary

Followed the client feedback handoff. Published the shapefile release, ran the
pipeline on the test area, settled the design decisions with the owner, then
built the multi-target pipeline and web support, the 30 m PMTiles export, the
MB and SK region and tiling groundwork, and a province summary file, with one
sub-agent per item. No new data is published on the live site yet.

## Completed (all merged to main)

- Release `test-area-shapefiles-v1` published (17 zips). Shapefile areas match
  the cached rasters for all years 2009 to 2025 to within 0.0001 km2.
- #37 SK/MB test area runs through the pipeline from a bbox window.
- #38, #41, #42 pasture as a fourth target, build plan, decisions, approved
  caveat wording (`docs/design/04_conversion_targets.md`).
- #39 ADR 0003 accepted (30 m layer). #40 Land Series note verified against the
  AAFC Land Use specification. #17 dependabot merged.
- #44 differencing-uncertainty caveat.
- #45 pipeline per-target conversion (crop, pasture, urban, barren), nested
  `converted_ha`, contract version 2.
- #47 web app reports each target separately (tabs, "also converted to" block,
  no combined total, CSV and report per target).
- #48 `python -m cropconv.export_tiles` writes 30 m converted pixels as PMTiles.
- #49 14 MB/SK farming-zone ecoregion pieces in `web/public/data/regions.json`.
- #50 earlier pasture and urban use removes a cell from the natural baseline,
  on by default.
- #51 Interlake MB second test window (`mb-interlake`).
- #52 100 km fixed tiles plus `index.json` region index (ADR 0004, contract
  version 3).
- #53 cells.json guideline raised to 10 MB raw.
- #54 `province_summary.json` (MB, SK, all) with a coverage flag.
- #43, #46 and this session's `docs/build-list.md` (the live build list).

## Current state

- Live site is unchanged from the previous session: Stettler data, flat
  contract. The new multi-target and tiled code is merged but has no published
  data, and the web app does not read `index.json` yet. Do not publish tiled
  data until item 18 lands.
- Measured sizes: SK/MB test area (28,800 km2) cells.json 5.98 MB raw, about
  0.6 MB gzipped with four targets. Interlake (10,000 km2) 2.15 MB raw, 0.24 MB
  gzipped. Province extrapolation about 300 to 360 MB raw. PMTiles for the test
  area: 11.1 MB crop only, 19.0 MB all targets (build about 4 minutes, 1.25 GB).
- SK/MB crop conversion at default filters with the new baseline rule:
  2011 baseline 18.3 percent (unreliable), 2016 baseline 4.8 percent, 2021
  baseline 1.7 percent of natural cover. Before the rule, 2016 was 5.6 and 2021
  3.4 percent.
- Item 19 merged (#55): global caveat that the by-class split is unreliable
  across years, and a note that the 2025 map classifies non-crop land
  differently. Existing data JSON picks these up on the next pipeline run.
- Web changes from #47 are covered by unit tests only, not checked in a browser.

## Findings that change how to read the data

- The split of natural cover by class is unstable between years. Interlake
  broadleaf forest goes from about 11,500 ha (2011) to 236,000 ha (2025) while
  shrubland falls from 237,000 to 17,000 ha, and forest plus shrubland together
  stay roughly constant. SK/MB wetland swings between 29,000 and 122,000 ha.
  Cause: ACI classifies non-crop land separately each year from changing sensors
  (AAFC's own non-agricultural accuracy for Manitoba is about 63 to 70 percent).
  Not a `classes.csv` error. Owner decision: keep four classes, add caveats.
- 2025 looks different in non-crop classes (shrubland nearly gone, wetland about
  doubled) in both windows. Owner decision: keep 2025 as latest, add a note.
- SK/MB 2011 natural cover is about 40 percent above 2016 (not present in the
  Interlake window), so the 2011 interval is unreliable there (caveat added).
- AAFC Land Use has no accuracy figures, no pasture class, merges grassland
  and shrubland, and is partly built from ACI (see the Land Series note).

## Decisions made (owner)

- Regions: ecoregions, farming zone only. Joint venture areas dropped.
- Provinces: pre-aggregated summary first, detail on request.
- Pasture reported as its own target, never added to crop. No combined total.
- Baseline exclusion for earlier pasture and urban use on in published data.
- Snapshot years stay 2011, 2016, 2021. Noise filter default unchanged.
- Publish the test-area data when checks pass. 30 m PMTiles committed to the
  repo for the test area.

## Next actions (see `docs/build-list.md`)

1. Item 18: web region picker, province card and tile loading (reads
   `index.json` and `province_summary.json`).
2. Item 9: 30 m map layer in the web app (source layer `converted`, properties
   `interval`, `target`, `class`, zoom 11 to 14).
3. Item 20: keyed `meta.target_caveats`, replacing positional pairing in
   `web/src/lib/targets.ts`.
4. Item 21: run all 14 farming-zone regions in tiled mode.
5. Items 5 and 6: noise sensitivity range in the report; 2011 caveat in the UI.
6. Item 11 (PR C): regenerate Stettler and the demo fixture, generate the tiled
   test area and Interlake window, publish, run `pages.yml` by hand, then item
   22 (browser check).

## Risks or decisions needed

- Province "totals" must not be shown as provincial until `coverage.complete`
  is true; only 4 of 14 regions are covered by the test area (3.5 percent).
- Region assignment uses coarse boundaries (1:1M ecoregions from 2003, Natural
  Earth provinces); edge cells are approximate, 5 km2 Interlake Plain SK piece
  dropped.
- Province-scale PMTiles needs tippecanoe or a tiled build (pure Python is slow).
- Release assets may not serve range requests, so tiles stay in the repo for now.
- Real phone, tablet and screen reader checks are still not done.
- Validation of conversion rates against independent sources (#6) is open.

## Working notes

- Python venv: `uv venv` works here; `python3 -m venv` does not (no ensurepip).
- markdownlint in CI wants compact tables (`|a|b|`), run it locally before
  pushing.
- `AUTO_MERGE_TOKEN` is unset, so PRs go BEHIND after another merges; use
  `gh pr update-branch <n>` and merge one at a time.
- A first full-year area check was killed for memory; stream one year at a time.
