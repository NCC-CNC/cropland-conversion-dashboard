# Pre-tiled 30 m conversion layer

## Status

Proposed

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
