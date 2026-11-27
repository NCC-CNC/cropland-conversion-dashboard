# Build list

Items that can be built now. One sub-agent per item, two at a time. Status
values: queued, running, in PR, merged, blocked. Items that need an owner
decision are listed at the bottom until settled, then move up. Updated
2026-11-27 (feedback close-out).

## Items

|#|Item|Issue|Depends on|Status|
|---|---|---|---|
|1|PR A: pipeline targets and contract (crop, pasture, urban, barren)|#27|none|merged (#45)|
|2|Region sizing for MB and SK|#28|none|done, ecoregions chosen|
|3|PR B: web app target support|#27|1|merged (#47), checked on the live site 2026-11-27 (desktop and 390 px)|
|4|Differencing warning in the global caveats|#31|none|merged (#44)|
|5|Record noise filter sensitivity range in the report|#3|1|merged (#57)|
|6|Show the test-area 2011 caveat prominently in the UI|#30|3|merged (#57)|
|8|PMTiles 30 m converted layer in the pipeline|#29|1|merged (#48)|
|9|Map layer for 30 m pixels under a selection size threshold (PMTiles committed to the repo for the test area)|#29|8|merged (#57)|
|11|PR C: regenerate Stettler and demo fixture, generate the tiled test area and Interlake window, publish|#30|3, 14, 18|merged (#58); live site checked 2026-11-27 (data files serve, area and region pickers work); demo fixture unchanged (flat synthetic v1)|
|12|Raise the cells.json guideline to 10 MB raw|#28|none|merged (#53)|
|13|Second test window, Interlake MB|#28|1|merged (#51)|
|14|Pasture and urban baseline exclusion on by default|#27|1|merged (#50)|
|15|Ecoregion boundaries (14 farming-zone pieces) in the pipeline|#28|none|merged (#49)|
|16|Fixed 100 km tiling plus a region index (ADR 0004)|#28|15|merged (#52)|
|17|Province summary file (MB, SK, all) with coverage flag|#28|15|merged (#54)|
|18|Web: region picker, province card (summary first, detail on request), tile loading|#28|3, 16, 17|merged (#57)|
|19|By-class split caveat and 2025 non-crop note|#2|none|merged (#55)|
|20|Keyed `meta.target_caveats` instead of pairing by position|#27|1, 3|merged (#57)|
|21|Run each farming-zone region in tiled mode (fetch rasters for all 14 regions)|#28|16|done 2026-11-27: full 14 region run, 79 tiles planned, 71 written (8 have no 2025 data), 427,740 cells, about 23 min over 4 resumed runs, 0.73 GB peak; tiles 106 MB raw (max 2.7 MB), 10.7 MB gzipped, outside the repo and not committed. Coverage first measured as written-cell area (0.712 overall, 4 of 14 regions at 0.9, misleading for crop-dominated regions), then re-measured as mapped area (ACI pixels with data in the latest year and the baseline per region, cache key v2): 0.791 overall, 10 of 14 regions covered; the 4 uncovered are boreal regions (mid-boreal lowland MB 0.18, lowland SK 0.50, uplands SK 0.50, Interlake 0.82 from the 2011 gap only) where the ACI genuinely maps less. The all-region 2011 caveat now describes the province-wide pattern; the older ACI years do not map the far north, so the tile size guard now warns instead of aborting. Guard fix merged (#60); mapped-area coverage in PR #61. Generated 14-region data is not published or committed|
|22|Browser check of the nested and tiled data (keyboard, tabs, mobile, screen reader, map shading)|#27|11|partly done 2026-11-27 with a headless browser on the live site: area and region pickers, draw and results, 2011 caution tab, four target tabs, 30 m layer under 500 km2 (and the size hint above it), report download, Methods and caveats tab, no horizontal overflow at 390 px, no script errors. Still needs the owner: real phone and tablet, screen reader, Word|
|23|Download the report as a Word document instead of Markdown||none|merged (#59); download verified on the live site, the file is a valid .docx with 12 tables; not yet opened in Word by the owner|

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
- Second test window: Interlake, Manitoba (done).
- 30 m PMTiles for the test area is committed to the repo.
- By-class split: keep four classes, add caveats only. Keep 2025 as latest year
  with a note.

## Feedback close-out (2026-11-27)

- SK/MB PMTiles rebuilt so its method text carries the persistence year.
- Shapefile zips verified against the cached rasters for all 17 years
  (`docs/design/06_shapefile_verification.md`).
- Live site checked with a headless browser (see item 22).

## Needs the owner

- Real phone, tablet and screen reader checks.
- Validate conversion rates against independent sources (#6).
- Judge region coverage on the 2016 and 2021 baselines only, not 2011? One line
  in `_coverage_rows`; Interlake would pass, the three northern boreal regions
  would not.
- Publish the 14-region data (102 MB) or restrict the province view to the
  farming zone only? Three Boreal Plains regions stay partial.
- Open the Word report in Word and check tables and coordinate blocks.
