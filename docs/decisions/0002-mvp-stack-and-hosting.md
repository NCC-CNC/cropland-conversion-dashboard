# MVP stack and hosting

## Status

Accepted

## Context

The MVP needs a draw-a-polygon web map that returns conversion summaries
instantly, hosted for free with no server. Issue #4 asks for a stack and
hosting choice.

## Decision

- Hosting: GitHub Pages, static files only, deployed by a GitHub Actions
  workflow.
- Front end: Vite, TypeScript and MapLibre GL JS, with a polygon draw tool and
  Turf for point-in-polygon.
- Data: a Python pipeline (`pipeline/`) downloads AAFC Annual Crop Inventory
  snapshots for a small test area, computes transitions, aggregates them onto
  a 1 km grid, and writes static JSON under `web/public/data/`. The browser
  sums the grid cells inside the drawn polygon. The file format is specified
  in `docs/design/02_mvp_data_contract.md`.

## Consequences

- No backend to run or pay for; every query is client-side.
- Results are approximate at the 1 km cell scale, so the UI must say so and
  the tool stays a screening aid, as the brief requires.
- The grid approach scales by adding one data folder per area, so staging by
  ecozone remains possible.
- Cell files must stay small enough to download quickly; large areas will need
  tiling or Parquet later.
