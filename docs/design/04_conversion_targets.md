# 04 Conversion targets beyond cropland

Status: proposal. Tracks issue #27. Requested in client feedback of 2026-11-26.

## Request

Summaries should report natural habitat converted to cropland and also natural
habitat converted to urban/developed and to exposed land/barren. Decision
(2026-11-26): report each target separately, not as one combined figure.
Greenhouse was not selected and is left out unless requested again.

## Proposed change

A "target" is the class a natural cell became by the latest snapshot. Targets:

- `crop` (current behaviour)
- `urban` (urban and developed)
- `barren` (exposed land and barren)
- `pasture` (pasture and forage, ACI 122), added 2026-11-26, see below

Natural classes stay as today: forest, grassland, wetland, shrubland.

### Data contract

`converted_ha` in `cells.json` gains a target level. Proposed shape, replacing
the class arrays with a nested map (contract version bump):

```json
"converted_ha": {
  "crop":   {"forest": [..], "grassland": [..], "wetland": [..], "shrubland": [..]},
  "urban":  {"forest": [..], "grassland": [..], "wetland": [..], "shrubland": [..]},
  "barren": {"forest": [..], "grassland": [..], "wetland": [..], "shrubland": [..]}
}
```

`natural_ha` is unchanged. `meta.json` gains `"targets": ["crop","urban","barren"]`
and a `contract_version`. The web app reads `targets` and treats a file without
it as crop only, so older areas keep working.

### Pipeline

Map ACI codes to targets in one table (with the existing class mapping). A cell
is natural at baseline if its code maps to a natural class, and converted to a
target if its latest code maps to that target.

### UI

- Headline card keeps "Habitat converted to cropland" as the primary figure,
  with the other targets shown as additional rows beneath it.
- Class table gets a target selector (tabs or columns). Percent is always of
  baseline natural hectares, and a cell cannot count in two targets.
- CSV and the downloadable report gain a target column.

## Pasture and forage as a fourth target

Decision (2026-11-26): report conversion to pasture and forage as its own
target, next to crop, instead of choosing one default. On the SK/MB test area,
counting ACI 122 as crop roughly doubles the 2011 to 2025 total (97.6k to
206.9k ha) and 2016 to 2025 (21k to 42k ha), so the choice matters more than
any filter setting.

- `crop` stays the headline and excludes ACI 122, as today. `pasture` is a
  separate row and tab, never added into the crop figure, and a cell counts in
  one target only.
- Same noise filter and persistence rules as crop, with 122 as the persistent
  class. Confidence is lower: native and tame grass are hard to separate, so
  some "converted to pasture" is reseeding of existing grassland. The UI badge
  says so, as for urban and barren.
- Size: four targets times four classes roughly doubles `cells.json` (3.3 MB
  for the test area today). Mitigate by writing zero arrays as `0` runs or
  omitting all-zero target/class pairs, and rely on Pages gzip. Re-check the
  5 MB guideline in the data contract before building.
- Existing `--pasture-is-crop` stays as a sensitivity option only.

## Build plan (crop, pasture, urban, barren)

Written 2026-11-26 against the code as it stands. Three small PRs, in order,
so the live site never sees a half-changed contract.

### PR A: pipeline and contract

- `classes.csv` / `classes.py`: add a `target` column (`crop`, `pasture`,
  `urban`, `barren`, or empty). `GROUPS` already has `pasture`; urban and
  barren need their own groups so ACI codes map to one target only. Extend the
  loader checks (one target per code, only non-natural codes have a target).
- `convert.py`: `is_crop` becomes `is_target(group_arr, target, params)`.
  `conversion_mask` takes a target and returns one mask per target; the same
  filters (persistence, patch size, majority) run per target. `pasture_is_crop`
  stays for sensitivity runs and only changes the crop target.
- Prior-use exclusion: `clean_baseline` today drops baseline natural cells that
  were crop earlier. Decide whether earlier pasture, urban or barren also
  removes a cell from the baseline (recommended: yes for pasture and urban,
  since a natural label on land that was already used is more likely a mapping
  error; keep a switch for the sensitivity table).
- Target precedence: one cell, one target. Targets are disjoint by
  construction because they key on the latest class, so no tie rule is needed.
  A cell that is natural, then crop, then pasture counts as pasture only if the
  persistence year is also pasture.
- `aggregate.py`: `converted_counts` is called per target. `run.py` writes
  `converted_ha` as `{target: {class: [...]}}`, drops all-zero target/class
  arrays, and writes `targets` and `contract_version` to `meta.json`.
- Per-target caveats in `CAVEATS` (pasture, urban, barren lower confidence),
  shown only when that target is present.
- Tests: mask disjointness across targets; a synthetic stack where the same
  cell flips natural to pasture, natural to crop and natural to urban; schema
  test that old flat files still validate; size test against the 5 MB guide.
- Docs: update `02_mvp_data_contract.md` (nested `converted_ha`, `targets`,
  `contract_version`, rule that a missing `targets` means crop only).

### PR B: web app

- `types.ts`: `converted_ha` is `ClassArrays | Record<string, ClassArrays>`;
  `Meta` gains optional `targets`. Add one normaliser in `data.ts` that turns
  the flat form into `{crop: ...}` on load, so the rest of the code sees one
  shape.
- `summary.ts`: `summarize` takes the active target (default `crop`) and also
  returns a compact per-target total for the headline rows. `grid.ts` (map
  shading) uses the active target.
- `csv.ts` and `report.ts`: add a target column and one results table per
  target, with the lower-confidence wording under pasture, urban and barren.
- `main.ts` / `render.ts`: headline card stays "Habitat converted to cropland",
  with pasture, urban and barren rows beneath it. Target tabs above the class
  table. Keep keyboard and screen reader behaviour of the existing table.
- Tests in `lib.test.ts` for the normaliser, per-target sums, and the CSV.

### PR C: data

- Regenerate `ab-parkland-stettler` and `demo-fixture` with the new contract
  and check the crop figures are unchanged to rounding.
- Generate `sk-mb-estevan-melville`, check `cells.json` size, and add it to
  `areas.json` once the owner agrees to publish. Run `pages.yml` by hand,
  since auto-merge does not deploy.

### Order of risk

1. Crop figures must not move: assert equality against the current Stettler
   output in PR A before anything else.
2. Pasture is the largest new number (about 2x crop on the test area), so it
   gets the clearest wording and is never summed into the crop headline.
3. Urban and barren may be dominated by roads, rail and well pads flickering
   between years. Look at the test-area maps before publishing those two.

## Risks

- Urban and barren classes in ACI are not mapped with the same care as crop.
  The "crop is mapped at 90%+" argument does not hold for them. The UI badge
  and caveats must say these figures are lower confidence.
- Small ACI classes flicker. The noise filter (issue #3) needs per-target
  thresholds, so settle it first.
- Roads, rail and wells may be mapped as barren or developed inconsistently
  between years. Check on the test area before publishing.

## Open questions

- Caveat wording below is a draft awaiting owner review.

## Decisions (2026-11-26, owner)

- Earlier pasture and urban use removes a cell from the natural baseline, as
  earlier crop does. Barren does not, because it flickers with roads and bare
  soil. Keep a switch for sensitivity runs.
- No combined "all conversion" total. Each target is reported separately.
- Build of PR A is deferred until the owner says to start.

## Draft caveat wording (for owner review)

Shown under the matching rows and in the methods report, only when that target
is present.

- Pasture and forage: "Conversion to pasture and forage is less certain than
  conversion to crop. Native grassland and seeded pasture look alike in the
  Annual Crop Inventory, so some of this may be existing grass that was
  reseeded or relabelled. It is not added to the cropland figure."
- Urban and developed: "Conversion to urban and developed land is mapped less
  accurately than crop. Roads, rail lines, well pads and small buildings can
  appear and disappear between years, so treat small values as uncertain."
- Barren and exposed land: "Conversion to barren and exposed land is the least
  reliable target. Bare soil, gravel, dry wetlands and recently cleared land
  are easily confused, and the label can change from year to year without a
  real change on the ground."

## PR A implementation notes (2026-11-26)

- Crop is unchanged: regenerating `ab-parkland-stettler` from cached rasters
  gives crop `converted_ha` identical to the published file, per cell (maximum
  difference 0.0 ha), and identical `natural_ha`.
- The prior pasture and urban exclusion is implemented as
  `FilterParams.exclude_prior_pasture_urban` (`--exclude-prior-pasture-urban`)
  but is off by default. Turning it on changes crop, because the baseline
  `natural_ha` shrinks. Stettler crop is unchanged at 3,464 ha for 2011 to
  2025 (no earlier snapshot) and falls from 3,888 to 1,257 ha for 2016 to 2025
  and from 1,599 to 560 ha for 2021 to 2025. The owner decision stands; the
  switch is meant to be turned on in the data PR (PR C), so the published crop
  numbers move once and with a documented reason.
- With `--pasture-is-crop` the pasture target is left out, so no hectare is
  counted twice.
- Size: Stettler `cells.json` is 0.40 MB raw (0.06 MB gzipped, was 0.21 MB raw)
  with all four targets. The SK/MB test area is 6.87 MB raw (0.68 MB
  gzipped), above the 5 MB guideline in the data contract, so publishing it
  needs the gzip argument accepted or coarser rounding.

## PR B implementation notes (2026-11-26)

- `normaliseCells` in `web/src/lib/data.ts` turns the flat `converted_ha` into `{crop: ...}` on load. A missing `meta.targets` means crop only, and such areas render with no target tabs and no extra rows.
- `summarize(cells, meta, indices, target)` returns the active target plus `targetTotals` for every target. `summarizeTargets` gives one summary per target for the CSV and the report. There is no combined total anywhere.
- Lower-confidence caveats are not duplicated in the web app. The pipeline appends one caveat per pasture, urban and barren target to the end of `meta.caveats`, in `targets` order, and the web app reads the last k entries. Reordering that list in the pipeline would break the pairing; a keyed `meta.target_caveats` would be sturdier.
- The active target is not stored in the share link. A reopened link starts on the cropland tab.
