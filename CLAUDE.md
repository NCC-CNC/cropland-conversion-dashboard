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

Idea and design stage. No code yet. Next milestone: a feasibility spike on
one ecozone (data download, 5 year snapshots, transition matrix, validation
against known conversion). Open GitHub issues are the live task tracker.

## Scope

In scope: Canada-wide (staged by ecozone or region) conversion summaries from
Annual Crop Inventory snapshots at roughly 5 year steps, user-drawn area
queries, hectare and percent outputs by natural cover class.

Not in scope (for now): new land cover classification, non-AAFC sources,
causal attribution of conversion, parcel-level or legal-grade results. Do not
expand scope without a design note in `docs/design/` or an ADR in
`docs/decisions/`.

## Stack

Not chosen yet. Likely shape: pre-computed regional transition summaries
(for example cloud-optimized GeoTIFF or zonal tables) behind a light web map
front end, so queries do not scan full rasters. Record the choice in an ADR.

## Commands

None yet. Fill in once the stack is chosen; `CONTRIBUTING.md` Setup should
match.

## Repo structure

See the tree; layout will be added once code exists.

## Working rules

- Branch from `main`; one short-lived branch per change. Open a pull request
  into `main`; CI must pass before merge.
- Conventional Commits (for example `feat: ...`, `fix: ...`, `chore: ...`,
  `docs: ...`).
- No em dashes in code, comments, docs, commit messages, or user-facing text.
- Significant technical or design decisions get an ADR in `docs/decisions/`.
- Design notes live in `docs/design/`; session handoffs in `docs/handoffs/`.
- Keep changes small and focused; update docs when behaviour or design changes.
