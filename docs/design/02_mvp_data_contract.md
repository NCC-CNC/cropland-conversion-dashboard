# 02 MVP Data Contract

The interface between the pipeline (`pipeline/`) and the web app (`web/`).
Either side may propose changes by editing this file in its PR.

## Files

Per area, under `web/public/data/<area_id>/`:

- `meta.json`: description of the area and run.
- `cells.json`: the aggregated grid.

Plus `web/public/data/areas.json`: `[{"id": "...", "name": "...", "bbox": [w,s,e,n]}]`.

## meta.json

```json
{
  "area_id": "sk-parkland-test",
  "name": "Saskatchewan Parkland test window",
  "bbox": [-106.5, 52.2, -105.7, 52.7],
  "cell_size_m": 1000,
  "snapshots": [2011, 2016, 2021, 2024],
  "latest": 2024,
  "natural_classes": ["forest", "grassland", "wetland", "shrubland"],
  "intervals": [
    {"from": 2011, "to": 2024, "years": 13},
    {"from": 2016, "to": 2024, "years": 8},
    {"from": 2021, "to": 2024, "years": 3}
  ],
  "method": "plain-language description of class mapping and noise filter",
  "source": "AAFC Annual Crop Inventory, OGL-Canada-2.0, URL",
  "generated": "ISO date",
  "caveats": ["list of strings shown in the UI"]
}
```

`intervals` always compare an earlier snapshot with the latest one.

## cells.json

Columnar, one entry per grid cell that has any natural cover at any baseline
or any conversion. Cell centroids are WGS84.

```json
{
  "lon": [..], "lat": [..],
  "area_ha": [..],
  "intervals": {
    "2011-2024": {
      "natural_ha": {"forest": [..], "grassland": [..], "wetland": [..], "shrubland": [..]},
      "converted_ha": {"forest": [..], "grassland": [..], "wetland": [..], "shrubland": [..]}
    },
    "2016-2024": {"...": "..."},
    "2021-2024": {"...": "..."}
  }
}
```

- All arrays within a file have equal length, hectares rounded to 2 decimals.
- `natural_ha[c]` is hectares of class c in the baseline snapshot, excluding
  cells that were already mapped as crop in an earlier snapshot (the pipeline
  treats those as fallow, forage rotation or mapping error; the earliest
  baseline has no earlier snapshot, so none are excluded there). Cells are
  therefore comparable between `natural_ha` and `converted_ha`.
- `converted_ha[c]` is hectares of class c in the baseline snapshot that are
  crop in the latest snapshot after the noise filter (method in meta).
- The web app computes, for a polygon: sum of cells whose centroid lies inside,
  percent = converted / natural, annual rate = converted / years.

## Rules

- No em dashes in any text field.
- Keep `cells.json` under about 5 MB for the MVP area.
- `snapshots` lists the baseline years and the latest year. The pipeline may
  also read the year before the latest as a persistence check; it is named in
  `method` but is not an interval baseline.
- `area_id` is free text (the test window is `ab-parkland-stettler`); the web
  app must read it from `areas.json`, not hard-code it.
