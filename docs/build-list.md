# Build list

Items that can be built now, in suggested order. One sub-agent per item, two at
a time. Status values: queued, running, in PR, merged, blocked. Items that need
an owner decision are listed at the bottom until settled, then move up.
Updated 2026-11-26.

## Items

|#|Item|Issue|Depends on|Status|
|---|---|---|---|---|
|1|PR A: pipeline targets and contract (crop, pasture, urban, barren)|#27|none|running|
|2|Region sizing: ecoregions, ecodistricts, joint venture areas for MB and SK|#28|none|running|
|3|PR B: web app target support (loader, summary, map, CSV, report, tabs)|#27|1|queued|
|4|Add AAFC differencing warning to the global caveats|#31|none|queued|
|5|Record noise filter sensitivity range in the report|#3|none|queued|
|6|Show test-area 2011 caveat prominently in the UI|#30|3|queued|
|7|Pipeline per region runs and per-region output files|#28|owner picks regions|blocked|
|8|PMTiles 30 m converted layer in the pipeline (test area first)|#29|1|queued|
|9|Map layer for 30 m pixels under a selection size threshold|#29|8|queued|
|10|Region picker and per-region loading in the web app|#28|7|blocked|
|11|PR C: regenerate Stettler and demo fixture, generate test area|#30|1, 3|queued|

## Needs the owner

- Region definition for MB and SK (after item 2 reports), and whether a
  province-wide view is wanted.
- Approve the draft caveat wording in `04_conversion_targets.md`.
- Approve publishing the test-area data to the live site (item 11).
- Real phone, tablet and screen reader checks.
- Validate conversion rates against independent sources (#6) and settle
  snapshot years and class scheme changes (#2).
