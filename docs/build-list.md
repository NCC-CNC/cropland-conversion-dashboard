# Build list

Items that can be built now. One sub-agent per item, two at a time. Status
values: queued, running, in PR, merged, blocked. Items that need an owner
decision are listed at the bottom until settled, then move up. Updated
2026-11-26.

## Items

|#|Item|Issue|Depends on|Status|
|---|---|---|---|---|
|1|PR A: pipeline targets and contract (crop, pasture, urban, barren)|#27|none|merged (#45)|
|2|Region sizing for MB and SK|#28|none|done, ecoregions chosen|
|3|PR B: web app target support (loader, summary, map, CSV, report, tabs)|#27|1|running|
|4|Add differencing warning to the global caveats|#31|none|merged (#44)|
|5|Record noise filter sensitivity range in the report|#3|1|queued|
|6|Show the test-area 2011 caveat prominently in the UI|#30|3|queued|
|8|PMTiles 30 m converted layer in the pipeline (test area first)|#29|1|running|
|9|Map layer for 30 m pixels under a selection size threshold|#29|8|queued|
|12|Raise the cells.json guideline to 10 MB raw in the data contract|#28|none|queued|
|13|Second test window, Interlake MB: area config, run, measure sizes|#28|1|queued|
|14|Turn on the pasture and urban baseline exclusion by default, method text states the change|#27|1|queued|
|15|Ecoregion boundaries (farming zone, 10 units) in the pipeline: fetch, clip, assign cells to regions|#28|none|queued|
|16|Fixed tiling of cells.json plus a region index file|#28|15|queued|
|17|Province summary files (one per province, pre-aggregated by target and interval)|#28|15|queued|
|18|Web: region picker, province summary card first with detail on request, tile loading|#28|3, 16, 17|queued|
|11|PR C: regenerate Stettler and demo fixture, generate the test area, publish|#30|3, 14|queued|

## Settled decisions (2026-11-26)

- Region type: ecoregions, farming zone only (Boreal Plains and Prairies).
  Joint venture areas are dropped as a partition (not in the client feedback).
- Provinces: both a pre-aggregated summary and detail on request, summary first.
- Baseline exclusion for earlier pasture and urban use is on in published data,
  with the change stated.
- cells.json guideline is 10 MB raw, since Pages serves it gzipped.
- Test-area data may be published when checks pass.
- Caveat wording in `04_conversion_targets.md` approved as drafted.
- Snapshot years stay 2011, 2016 and 2021 (#2).

## Needs the owner

- Real phone, tablet and screen reader checks.
- Validate conversion rates against independent sources (#6).
