# Pipeline

Builds the static data for the dashboard from AAFC Annual Crop Inventory (ACI)
snapshots. Output goes to `web/public/data/` in the format fixed by
`docs/design/02_mvp_data_contract.md`.

## Run

```bash
cd pipeline
python3 -m venv .venv && . .venv/bin/activate   # or: uv venv .venv
pip install -r requirements.txt                  # or: uv pip install -r requirements.txt
python -m cropconv.run                           # fetch (cached), compute, write JSON
python -m cropconv.run --sensitivity             # also print the filter sensitivity table
python -m pytest                                 # tests
```

The first run downloads five clipped rasters (about 1.8 million pixels each)
into `pipeline/cache/`, which is gitignored. Later runs reuse the cache. A
full run takes about 30 seconds. Never commit rasters.

Useful flags: `--latest YEAR`, `--min-patch-ha X`, `--no-persistence`,
`--majority`, `--keep-prior-crop`, `--exclude-prior-pasture-urban`, `--pasture-is-crop`,
`--targets crop,pasture,urban,barren`, `--out DIR`.

## What it does

1. Asks the AAFC ImageServer for a clipped export of each year over a 40 km
   window (`fetch.py`). Requests use EPSG:3978 (NRCan Lambert Conformal
   Conic), 30 m pixels, one band, `U8`, nearest neighbour. Nothing national is
   downloaded.
2. Checks each year: the service legend labels (in code order) must match
   `classes.csv`, every pixel value must be a legend code (so no colour
   mapping or interpolation), and the window must have data.
3. Maps codes to groups with `classes.csv` (`classes.py`).
4. Computes converted pixels per baseline year (`convert.py`).
5. Sums pixels onto a 1 km grid aligned to EPSG:3978, using true ground area
   (the projection areal scale is applied per cell), and writes WGS84 cell
   centroids (`aggregate.py`, `run.py`).

## Test window

Alberta Parkland near Stettler, about 40 x 40 km (1,600 km2), centred near
52.3 N, 112.7 W (id `ab-parkland-stettler`).

Why: it sits in the Aspen Parkland to Central Parkland transition, where
native grassland, shrubland and wetland remnants (about 20 percent of the
window) are interspersed with annual cropland, so grassland and wetland to
crop conversion is plausible. I compared five 40 km candidate windows in
Saskatchewan and Alberta for baseline natural share and found this one had
the most natural cover (about 20 percent against 8 to 13 percent) with all
four natural classes present. ACI has dense ground truth here from provincial
crop insurance data.

## Data access notes

- Years on the service: 2009 to 2025. Used: 2011, 2016, 2021, 2024 and 2025.
  The latest published year is 2025 (found by listing the service).
  2024 is read only as the persistence year for the 2025 comparisons and is
  not an interval baseline, so the contract `snapshots` are 2011, 2016, 2021
  and 2025.
- The ImageServer stores the mosaic in Web Mercator (30 m Mercator units, so
  about 18 m on the ground at this latitude). We request EPSG:3978 at 30 m
  with nearest neighbour, so the service resamples once. Values are
  unmodified class codes, but about 3 percent of boundary pixels can differ
  from the provincial GeoTIFF grid (checked by comparing a half pixel
  shifted request). Because every year is resampled the same way, the
  comparison between years is consistent. The provincial GeoTIFFs under
  `agriculture.canada.ca/atlas/data_donnees/annualCropInventory/data_donnees/tif/`
  are large provincial zips, so they are not used.
- The 1 km cells hold 33 or 34 pixels per side (a 30 m pixel is assigned to the
  cell containing its centre). `area_ha` is the true ground area of the
  pixels in the cell. The window is a 40 km square in EPSG:3978, which is a
  slightly rotated parallelogram in longitude and latitude, so `bbox` is the
  bounding box of its corners.

## Class harmonization

`classes.csv` is the version controlled mapping (code, label, group, target, natural
class, note), copied from the official AAFC legend CSV. A per-year legend
check compares the service legend labels, in code order, with it, and
the run prints a warning if they differ.

| Group | Codes |
| --- | --- |
| natural: forest | 200, 210, 220, 230 |
| natural: grassland | 110 |
| natural: wetland | 80 |
| natural: shrubland | 50 |
| crop | 120, 121, 130, 131, and 132 to 199 (all named crops, including fallow) |
| pasture | 122 (pasture and forages) |
| urban | 34 (urban and developed) |
| barren | 30 (exposed land and barren) |
| other | 10 cloud, 20 water, 35 greenhouses, 60 burnt, 85 peatland |

Decisions:

- Code 120 (undifferentiated agriculture) is crop. It marks agricultural land
  where ground data were missing, and it is not natural.
- Code 130 (too wet to be seeded) and 131 (fallow) are crop: they are
  cultivated land inside the rotation.
- Code 122 (pasture and forages) is NOT crop by default. ACI folds hay,
  alfalfa and tame grass into it. In this window the area mapped as 122 swings
  between 11 and 25 percent from year to year and swaps with grassland (110),
  so counting it as crop would turn classification noise between two grass
  classes into "conversion" (sensitivity row 7 below shows the size of the
  effect). The cost is that conversion of native grassland to tame pasture or
  hay is not detected, so results are conservative on that pathway.
- Code 85 (peatland) is exploited peatland in the ACI, and 60 (burnt area) is a
  disturbance state, so neither is natural cover.
- The ACI does not separate native grassland from tame grass. The grassland
  class here is "grassland as mapped".

## Conversion definition and filter default

A pixel is converted for interval B to L when all of these hold:

1. It is natural in baseline snapshot B (class from the baseline).
2. It is crop in the latest snapshot L.
3. Persistence: it is also crop in the most recent snapshot between B and L.
   This is 2024 for every interval here. If no snapshot lies between, the
   check is skipped.
4. Prior crop exclusion: it was not crop in any snapshot before B. Cells that
   were crop earlier and look natural in B are far more likely fallow, forage
   rotation or mapping error. The same exclusion is applied to the baseline
   natural hectares so converted never exceeds natural. The 2011 baseline has
   no earlier snapshot, so it is not filtered this way.
5. Patch size: it belongs to a connected patch (8 neighbours) of converted
   pixels of at least 0.5 ha (6 pixels), counted across the whole window.
   Patches cut by the window edge are judged on their visible part.

Default: persistence on, 0.5 ha minimum patch, prior crop exclusion on,
majority filter off, pasture not crop. All are parameters of
`cropconv.convert.FilterParams` and flags of `cropconv.run`.

## Conversion targets

The pipeline reports natural cover converted to four targets, each on its own
and never summed: `crop`, `pasture` (122), `urban` (34) and `barren` (30). A
target is the class a natural cell has in the latest snapshot, so targets are
disjoint. The same filters (persistence, patch size, majority) run per
target, and persistence needs the target class in the persistence year too.
Design: `docs/design/04_conversion_targets.md`.

- `--pasture-is-crop` is a sensitivity option that changes the crop target
  only; the pasture target is then left out so nothing is counted twice.
- Prior use exclusion: earlier crop removes a cell from the natural baseline
  (default on). Earlier pasture and urban use should too (owner decision
  2026-11-26), switch `--exclude-prior-pasture-urban`. It is off by default
  for now because it changes crop figures (Stettler 2016 to 2025 crop falls
  from 3,889 to 1,258 ha, see sensitivity row 8), so it is turned on together
  with the data regeneration. Earlier barren never removes a cell.
- `cells.json` writes `converted_ha` as `{target: {class: [...]}}`, leaves out
  all-zero arrays, and `meta.json` lists `targets` and `contract_version`.
  Caveats for pasture, urban and barren appear only when that target is
  present.

## Sanity check of the real output

Whole window, default filter, ha converted (percent of baseline natural):

| Interval | Natural ha | Converted ha | Percent | Per year |
| --- | --- | --- | --- | --- |
| 2011 to 2025 | 35,300 | 3,464 | 9.8 | 247 ha |
| 2016 to 2025 | 48,808 | 3,888 | 8.0 | 432 ha |
| 2021 to 2025 | 41,019 | 1,599 | 3.9 | 400 ha |

By class for 2016 to 2025: grassland 2,722 ha (11.9 percent), wetland 715 ha
(5.7), shrubland 291 ha (3.3), forest 160 ha (3.4).

From 2016 and 2021 baselines the loss is about 400 to 430 ha per year, roughly
1 percent of remaining natural cover per year. That is high but plausible for
parkland where the remnants are unprotected, and the two intervals agree. With
latest year 2024 instead of 2025 the rate is again 410 to 420 ha per year
(`--latest 2024`), so the 2025 map does not drive the result.

Worries to keep in mind:

- The 2011 baseline is not comparable. Natural cover is 35,300 ha in 2011
  against 48,800 ha (default, 2016) and 41,000 ha (2021), because 2011 maps 25
  percent of the window as pasture and only 7.6 percent as grassland (2016:
  11 percent and 17 percent). The 2011 interval therefore understates
  conversion and its percentages should not be compared with the others.
- The class mix drifts between years even in the middle of the series:
  grassland is 17, 13, 3.7 and 5.6 percent in 2016, 2021, 2024 and 2025, and
  shrubland nearly vanishes in 2025 (0.07 percent against 8.6 percent in 2024,
  with broadleaf forest rising to 7.9 percent). Most of this is class
  confusion among natural and pasture classes, not land change. The converted
  hectares only count cells that become crop, which are mapped more stably, but
  the split by natural class (for example shrubland against forest) is
  unreliable and the UI should lean on the total.
- Percent values depend on a baseline natural area that is itself noisy.

## Sensitivity to filter settings

Converted ha over the whole window (percent of that row's baseline natural ha),
from `python -m cropconv.run --sensitivity`:

| Setting | 2011 to 2025 | 2016 to 2025 | 2021 to 2025 |
| --- | --- | --- | --- |
| 1. No filter at all | 6,929 (19.6%) | 15,187 (24.8%) | 10,919 (20.3%) |
| 2. Persistence only | 3,928 (11.1%) | 8,125 (13.3%) | 4,797 (8.9%) |
| 3. Persistence + 0.5 ha patches | 3,464 (9.8%) | 5,507 (9.0%) | 2,878 (5.4%) |
| 4. Default: 3 + exclude prior crop | 3,464 (9.8%) | 3,889 (8.0%) | 1,600 (3.9%) |
| 5. As default, 2 ha patches | 2,849 (8.1%) | 3,222 (6.6%) | 1,309 (3.2%) |
| 6. As default, plus 3x3 majority filter | 2,687 (7.6%) | 2,928 (6.0%) | 1,203 (2.9%) |
| 7. As default, pasture/forage counted as crop | 7,770 (22.0%) | 3,833 (12.5%) | 1,885 (7.1%) |
| 8. As default, also exclude prior pasture and urban | 3,464 (9.8%) | 1,258 (4.2%) | 560 (2.1%) |

Without any filter, the raw "natural to crop" transition is 20 to 25 percent of
natural cover, which is mostly noise. Persistence removes about half of it,
the patch size and prior crop filters remove a further 20 to 45 percent. The
default sits in the middle of the plausible range (rows 4 to 6 differ by about
a third). The result is a conservative, filtered estimate, not a validated one:
no independent conversion estimate was compared (that is the feasibility
spike's validation step, issue 6).

## Layout

```text
pipeline/
  classes.csv        class mapping (version controlled)
  cropconv/          fetch, classes, convert, aggregate, run
  tests/             pytest: mapping, conversion logic, output schema
  requirements.txt
  cache/             downloaded rasters (gitignored)
  .venv/             virtual environment (gitignored)
```

To add an area, add an entry to `AREAS` in `cropconv/run.py` (id, name,
centre) and rerun. `areas.json` is merged by id.

## Raw per-year shapefiles (test area)

`python -m cropconv.export_shapes [--years 2024]` writes one zipped shapefile
per ACI year for the Estevan SK, Melita MB, Russell MB, Melville SK test area
into `pipeline/exports/` (gitignored). One polygon per connected patch of an
original ACI class code, EPSG:3978, attributes YEAR, CODE, LABEL, GRP. Upload
the zips to a GitHub Release; never commit them. The 2009 and 2010 snapshots
are 56 m in the source.
