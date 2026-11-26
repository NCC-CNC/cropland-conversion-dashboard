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
