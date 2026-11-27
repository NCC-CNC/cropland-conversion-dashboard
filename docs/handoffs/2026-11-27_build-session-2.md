# Session Handoff: 2026-11-27 (build session 2)

## Summary

Worked the build list with one sub-agent at a time on a single branch for the
code (PR #57), then a data PR (#58), a Word report PR (#59), a guard fix
(#60) and a coverage measure PR (#61). Ran the full 14-region tiled run
outside the repo. Triggered a Pages run after #57 and again after #58 and #59.

## Completed

- #57 merged: noise filter sensitivity block (#5), per-interval caution note
  in the UI (#6), 30 m PMTiles layer (#9), region picker, province card and
  tile loading (#18), keyed `meta.target_caveats` (#20), tiled region runner
  `python -m cropconv.regional` (#21).
- #58 merged: regenerated Stettler, tiled SK/MB test area (6 tiles) and
  Interlake (4 tiles) with province summaries, 14.4 MB PMTiles for the test
  area, loader errors that name the file and cause, 2011 caveat corrected to
  about two thirds for the SK/MB test area, README figures refreshed.
- #59 merged: Download report now gives a Word file (docx library, loaded on
  click). Markdown view kept for tests only.
- #60 merged: older ACI years that map little of a northern tile now warn
  instead of aborting the tile.

## In flight

- #61 (open): region coverage by mapped area, all-region 2011 caveat rewritten.
  10 of 14 regions covered; `complete` stays false for MB, SK and overall.
  Not covered: mid-boreal lowland MB (0.18), mid-boreal lowland SK (0.50),
  mid-boreal uplands SK (0.50), Interlake Plain MB (0.82, fails 2011 only).

## Current state

- Pages was triggered after #58 and #59 but the live site has not been checked.
  Run `gh workflow run pages.yml --ref main` after #61 only if web code
  changes (it does not).
- The 14-region data is in `~/cropconv-out-14b` (102 MB, 71 of 79 tiles,
  427,740 cells), cache in `~/cropconv-cache` (about 4 GB rasters). Not
  committed or published.
- Full run cost: about 5 minutes from cached rasters, about 23 minutes with
  downloads, 0.73 GB peak memory.
- Province natural cover (ha, 2011 / 2016 / 2021): MB 5.91 M / 7.08 M / 7.18 M,
  SK 12.54 M / 13.06 M / 13.92 M. Crop conversion to 2025 as percent of natural:
  MB 6.4 / 2.2 / 0.6, SK 2.9 / 0.6 / 0.2 (2011, 2016, 2021 baselines).
- Province-wide, 2011 natural cover is lower than 2016 (MB 16 percent, SK 4
  percent; 2011 does not map the far north) but 2011 conversion is 2.5 to 4.5
  times the 2016 interval. The SK/MB test area differs: 2011 natural cover is
  about two thirds above 2016 there.

## Findings

- ACI older years do not map the far north, so a one-year data gap is real, not
  a bad download. A truncated download of an older year now passes with only a
  warning (risk accepted in #60).
- The earlier dev server error "Unexpected token '<'" was a server started
  before the data folders existed; restart it after copying data in. Do not use
  `pkill -f vite` from the agent shell (it kills its own shell).

## Next actions

1. Review and merge #61.
2. Decide: judge coverage on the 2016 and 2021 baselines only (one line in
   `_coverage_rows`)?
3. Decide: publish the 14-region data (102 MB) or restrict to the farming zone;
   three Boreal Plains regions stay partial.
4. Item 22 browser check on the live site: area picker, province card
   ("covered regions only"), 30 m layer under 500 km2, 2011 caution tab, and the
   Word report opened in Word.
5. Re-export the SK/MB PMTiles so its method text carries the persistence years
   (code fixed in #58, committed file not yet rebuilt).
6. Publish the shapefile release (#30), and owner checks: phone, tablet,
   screen reader, validation of conversion rates (#6).

## Risks or decisions needed

- Province totals must not be shown until `coverage.complete` is true.
- The demo fixture is still flat v1 and has no keyed caveats or sensitivity
  block (generator not changed).
- No new web tests cover the region picker UI in a browser; only unit tests.

## Working notes

- `uv venv` for Python. `pipeline/.venv` has pytest.
- Auto-merge merges PRs once CI passes, often before manual merge is needed.
- Sub-agents were run one at a time sharing one working tree, on disjoint
  directories; commits used explicit paths.
