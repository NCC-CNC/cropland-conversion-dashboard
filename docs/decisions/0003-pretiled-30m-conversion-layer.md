# Pre-tiled 30 m conversion layer

## Status

Accepted (2026-11-26), after the hosting check below.

## Context

Client feedback (2026-11-26) asks to see the actual 30 m pixels that were
converted. ADR 0002 chose a static site with a pre-computed 1 km grid and no
backend. Computing 30 m results on demand would need a server and could take
minutes, which would need an estimated-time prompt. The client also suggested
limiting the detail to selections under about 500 km2 if processing is slow.

## Decision

Build a 30 m conversion layer in the pipeline and publish it as static vector
or raster tiles (PMTiles), shown on the map only when the selection is small
(starting threshold 500 km2, adjustable). No backend is added. Decision made
with the owner on 2026-11-26.

## Consequences

- No waiting and no confirm prompt: pixels appear instantly at small sizes.
- Pipeline work and storage grow. Test on the Estevan to Melita to Russell to
  Melville area (issue #30) and measure before extending province wide.
- Summary numbers stay on the 1 km grid, so the pixel layer and the totals may
  differ slightly at edges. The UI must say which is which.
- Hosting must support HTTP range requests (GitHub Pages does). Size may
  force tiles onto a release asset or object store later.
- If large areas must show pixels, a backend would need a new ADR.

## Hosting check (2026-11-26)

Converted 30 m pixels on the SK/MB test area (28,800 km2) at the default noise
filter, from the pipeline's own masks, vectorised as 4-connected patches:

|Interval|Converted ha|Patches|Vertices|Raw GeoJSON (est.)|
|---|---|---|---|---|
|2011 to 2025|96,800|43,000|706,000|about 13 MB|
|2016 to 2025|21,200|26,500|272,000|about 5 MB|
|2021 to 2025|12,800|15,200|164,000|about 3 MB|

About 21 MB raw for the three intervals. PMTiles compression and zoom
simplification should bring that well under that figure, but this was not
built, so treat it as an upper bound for the test area. Scaling by area to all
of Manitoba and Saskatchewan agricultural land suggests tens to a few hundred
MB, which fits under the Pages limit of about 1 GB but would bloat the repo.
Plan: keep test-area tiles in the repo; for province scale host the PMTiles as
a release asset or object store (range requests are required). Re-measure
with a real PMTiles build before committing to province scale.

## Measured (2026-11-26)

Real build with `python -m cropconv.export_tiles` on the SK/MB test area
(intervals 2011, 2016, 2021 to 2025, default filters, zoom 11 to 14, gzip MVT,
pure Python). Crop hectares match the 1 km pipeline (97,617, 21,324 and
12,932 ha).

|Build|Patches|PMTiles size|Wall time|Peak memory|
|---|---|---|---|---|
|Crop only, 3 intervals|133,000|11.1 MB|1 min 52 s|1.1 GB|
|All 4 targets, 3 intervals|250,000|19.0 MB|4 min 8 s|1.3 GB|

Tiles per zoom (non-empty):

|Zoom|11|12|13|14|Total|
|---|---|---|---|---|---|
|Crop only|216|783|2,906|9,148|13,053|
|All targets|216|792|2,996|10,218|14,222|

- Crop only is 11 MB against the 21 MB raw GeoJSON estimate, so compression
  and zoom simplification help, but by about half, not by an order of
  magnitude. Patches are split per natural class and kept 4-connected, so the
  count is higher than the estimate (133,000 against 85,000).
- Pasture is the largest target (about 100,000 patches), which is why adding
  the other three targets adds 8 MB. The test area at all targets is better
  hosted as a release asset than committed; province scale (tens of times
  larger) must not be committed.
- The Python tile build is slow at scale (about 4 minutes here). Province
  scale would want tippecanoe or a tiled build.
