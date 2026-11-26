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

- Is a single "other conversion" total also wanted for the headline?
- Does the confidence caveat need wording from the owner?
- Should earlier pasture, urban or barren remove a cell from the natural baseline (see PR A)?
