# 02 MVP Data Contract

The interface between the pipeline (`pipeline/`) and the web app (`web/`).
Either side may propose changes by editing this file in its PR.

## Files

Per area, under `web/public/data/<area_id>/`:

- `meta.json`: description of the area and run.
- `cells.json`: the aggregated grid.

Plus `web/public/data/areas.json`: `[{"id": "...", "name": "...", "bbox": [w,s,e,n]}]`.

## Tiled areas (contract version 3)

An area can instead be written as fixed 100 km tiles (`tiles/<col>_<row>.json`)
and an `index.json`, with no `cells.json`; `meta.json` then has
`contract_version` 3, `tiled: true` and `tile_km`. Each tile has the
`cells.json` shape below plus a `region` integer per cell. A reader treats an
area without `tiled` (and without `index.json`) as before, so version 1 and 2
areas keep working. Format and sizes: `05_regional_partitioning.md` and
`docs/decisions/0004-tiled-cell-data.md`.

A tiled area in Manitoba or Saskatchewan also has `province_summary.json`
(`kind: province_summary`, still contract version 3, so no version bump: it is
an added optional file that older readers ignore). It holds pre-summed totals
per province (`MB`, `SK`, `all`), per interval, target and class, with
percent, plus a `coverage` block of regions run and the fraction of the
farming zone covered, and `method`, `caveats` and dates copied from
`meta.json`. A reader must call the totals provincial only when
`provinces.<code>.coverage.complete` is true. Shape and rules:
`05_regional_partitioning.md` (Province summary).

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
  "targets": ["crop", "pasture", "urban", "barren"],
  "contract_version": 2,
  "intervals": [
    {"from": 2011, "to": 2024, "years": 13},
    {"from": 2016, "to": 2024, "years": 8},
    {"from": 2021, "to": 2024, "years": 3}
  ],
  "method": "plain-language description of class mapping and noise filter",
  "source": "AAFC Annual Crop Inventory, OGL-Canada-2.0, URL",
  "generated": "ISO date",
  "caveats": ["list of strings shown in the UI"],
  "target_caveats": {"pasture": "caveat text", "urban": "caveat text", "barren": "caveat text"},
  "sensitivity": {
    "target": "crop",
    "note": "plain-language caveat",
    "settings": [
      {"id": "no_filter", "label": "1. No filter at all", "is_default": false,
       "intervals": {"2011-2024": {"converted_ha": 6929.0, "natural_ha": 35300.0, "percent": 19.63}}},
      {"id": "default", "label": "5. Default: ...", "is_default": true, "intervals": {"...": "..."}}
    ]
  }
}
```

`intervals` always compare an earlier snapshot with the latest one.

`sensitivity` is optional and additive (issue 3, 2026-11-26); readers must
ignore it if absent. It records whole-window crop conversion under eight
preset noise filter settings (ids `no_filter`, `persistence`, `patch_0_5`,
`prior_crop`, `default`, `patch_2`, `majority`, `pasture_as_crop`), each as
hectares converted, the setting's own baseline natural hectares and the
percent, per interval key (`from-to`, same keys as `intervals`). Exactly one
setting has `is_default: true`: the documented default preset, which equals
the filters actually applied unless the run overrode them (see `method`). Only
crop is covered. Values are totals for the whole area window, not for a drawn
polygon, so they show the range of the filter choice, not area specific
uncertainty.

`targets` lists the classes that natural cover can be converted to, a subset
of `crop`, `pasture`, `urban`, `barren` that always includes `crop`.
`contract_version` is 2 for the nested `converted_ha` below. A file without
`targets` (and without `contract_version`) is version 1: `converted_ha` is the
flat class map and means crop only. Readers must treat a missing `targets` as
`["crop"]`, so older areas keep working.

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
      "converted_ha": {
        "crop":    {"forest": [..], "grassland": [..], "wetland": [..], "shrubland": [..]},
        "pasture": {"grassland": [..], "wetland": [..]},
        "urban":   {"grassland": [..]}
      }
    },
    "2016-2024": {"...": "..."},
    "2021-2024": {"...": "..."}
  }
}
```

- All arrays within a file have equal length, hectares rounded to 2 decimals.
- `natural_ha[c]` is hectares of class c in the baseline snapshot, excluding
  cells that were already mapped as crop, pasture or forage, or urban in an
  earlier snapshot (the pipeline treats earlier crop as fallow, forage rotation
  or mapping error, and earlier pasture or urban as tame grass, hay or developed
  land; the earliest baseline has no earlier snapshot, so none are excluded
  there). Earlier barren never excludes a cell. Cells are
  therefore comparable between `natural_ha` and `converted_ha`.
- `converted_ha[t][c]` is hectares of natural class c in the baseline
  snapshot that are in target t in the latest snapshot after the noise filter
  (method in meta). Each target is reported on its own and there is no
  combined total. Targets are disjoint, so a hectare counts in one target at
  most.
- All-zero arrays are left out: a class missing under a target, or a target
  missing from an interval, means zero. `natural_ha` always has every class.
- Version 1 files have the flat form `converted_ha[c]` (crop only), with every
  class present:
  `"converted_ha": {"forest": [..], "grassland": [..], "wetland": [..], "shrubland": [..]}`.
- The pasture and urban exclusion is on by default (owner decision
  2026-11-26) and is switched off with `--keep-prior-pasture-urban`; `method`
  says which exclusions were applied, and when the rule is on it also says that
  figures are lower than in earlier versions. Earlier barren never excludes a
  cell.
- Caveats for pasture, urban and barren are in `meta.caveats` only when that
  target is in `targets`, and also in `meta.target_caveats`, an object keyed
  by target id (only for targets present). This is additive, so
  `contract_version` is unchanged. Readers use `target_caveats` and fall back,
  for files without it, to pairing the last k entries of `caveats` with the
  lower-confidence targets in `targets` order. That fallback is wrong for
  areas that append `extra_caveats`, which the keyed form fixes.
- The web app computes, for a polygon: sum of cells whose centroid lies inside,
  percent = converted / natural, annual rate = converted / years.

## Rules

- No em dashes in any text field.
- Keep `cells.json` under about 10 MB raw (owner decision, 2026-11-26; was
  about 5 MB). GitHub Pages serves it gzipped, so the transfer size is what
  matters. Omitting all-zero arrays helps. For tiled data the guideline is
  about 2 MB raw per tile, a guideline and not a hard limit. Measured, all
  four targets:

  |Data|Raw|Gzipped|
  |---|---|---|
  |SK/MB test area, single `cells.json`|5.98 MB|about 0.6 MB|
  |Interlake window, single `cells.json`|2.15 MB|0.24 MB|
  |Tiled 100 km tile, largest|about 1.8 MB|about 0.2 MB|

- `snapshots` lists the baseline years and the latest year. The pipeline may
  also read the year before the latest as a persistence check; it is named in
  `method` but is not an interval baseline.
- `area_id` is free text (the test window is `ab-parkland-stettler`); the web
  app must read it from `areas.json`, not hard-code it.

## Optional 30 m pixel layer

The web app looks for `web/public/data/<area_id>/converted.pmtiles` (ADR 0003).
It is optional: when the file is missing or unreadable the pixel toggle and
legend stay hidden and nothing else changes. The archive is PMTiles v3 vector
tiles, zoom 11 to 14, one source layer `converted`, with properties `interval`
(baseline year), `target` and `class`. The layer shows only when a selection is
500 km2 or smaller and the map is at zoom 11 or closer.
