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
