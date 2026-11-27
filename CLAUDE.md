# CLAUDE.md

Working rules and durable context for this project. This file is loaded into
context automatically, so keep it to direction and rules, not a task list.

## Project name

Cropland Conversion Dashboard

## Project purpose

An online dashboard where a user selects an area (cursor or polygon) and
immediately sees summary statistics on land conversion to cropland: hectares
and percent of natural habitat (forest, grassland, wetland) converted to crop
between Agriculture and Agri-Food Canada (AAFC) Annual Crop Inventory
snapshots. Conservation practitioners currently rely on coarse regional
reports when justifying grants; this gives them a quick, area-specific answer.

The core idea: crop is mapped with high accuracy (reported 90%+) in the
Annual Crop Inventory, so comparing a recent crop map backward against
earlier ones identifies which cells were not crop before and are crop now.
See `docs/design/00_project_brief.md` for the full brief.

## Project status

MVP live on GitHub Pages: web app in `web/`, real ACI data for the Stettler
window plus a tiled SK/MB test area and Interlake window (100 km tiles,
four conversion targets: crop, pasture, urban, barren). The web app has a region
picker, province card and an optional 30 m pixel layer, and the report downloads
as a Word file. The 14-region MB/SK farming-zone run is published as `mb-sk-farming-zone`
(10 of 14 regions covered by mapped area, so province totals stay labelled
partial). See `docs/build-list.md` and
`docs/handoffs/2026-11-27_build-session-2.md`. Merges by the auto-merge workflow
do not trigger Pages; run `gh workflow run pages.yml --ref main` until
`AUTO_MERGE_TOKEN` is set. Open GitHub issues and the build list are the live
task tracker.

## Scope

In scope: Canada-wide (staged by ecozone or region) conversion summaries from
Annual Crop Inventory snapshots at roughly 5 year steps, user-drawn area
queries, hectare and percent outputs by natural cover class.

Not in scope (for now): new land cover classification, non-AAFC sources,
causal attribution of conversion, parcel-level or legal-grade results. Do not
expand scope without a design note in `docs/design/` or an ADR in
`docs/decisions/`.

## Stack

Static site on GitHub Pages: Vite, TypeScript, MapLibre GL JS, terra-draw
(polygon drawing) and Turf, in `web/`. It sums pre-computed 1 km grid cells
(JSON under `web/public/data/`) inside the drawn polygon; no backend. The data
format is the contract in `docs/design/02_mvp_data_contract.md`. See
`docs/decisions/0002-mvp-stack-and-hosting.md`.

## Commands

Run from `web/` (Node 20.19 or newer):

- `npm ci` then `npm run dev` for the dev server.
- `npm run typecheck`, `npm test`, `npm run build`: what CI runs.
- `npm run fixture` regenerates the synthetic demo data.

Run from `pipeline/` (Python 3.12 or newer, venv with
`pip install -r requirements.txt`):

- `python -m cropconv.run` fetches (cached), computes and writes the JSON.
- `python -m pytest` runs the tests (CI runs these).

## Repo structure

- `web/`: the static web app (`src/lib/` holds pure, tested logic).
- `web/public/data/<area_id>/`: per-area `meta.json` and `cells.json`, plus
  `areas.json`. Written by the pipeline; `demo-fixture/` is synthetic.
- `pipeline/`: Python pipeline from AAFC ACI snapshots to the grid JSON.
- `docs/`: design notes, ADRs, handoffs.

## Working rules

- Branch from `main`; one short-lived branch per change. Open a pull request
  into `main`; CI must pass before merge.
- Conventional Commits (for example `feat: ...`, `fix: ...`, `chore: ...`,
  `docs: ...`).
- No em dashes in code, comments, docs, commit messages, or user-facing text.
- Significant technical or design decisions get an ADR in `docs/decisions/`.
- Design notes live in `docs/design/`; session handoffs in `docs/handoffs/`.
- Keep changes small and focused; update docs when behaviour or design changes.
