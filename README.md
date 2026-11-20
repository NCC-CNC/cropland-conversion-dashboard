# Cropland Conversion Dashboard

An online dashboard to select an area on a map and quickly see how much
natural habitat (forest, grassland, wetland) was converted to cropland, based
on the AAFC Annual Crop Inventory.

**Status:** idea and design stage; no code yet. See
[`docs/design/00_project_brief.md`](docs/design/00_project_brief.md).

## Why

Rates of land conversion are needed regularly for conservation planning and
grant justification, but most available figures are coarse regional estimates.
Annual Crop Inventory crop mapping is highly accurate, so comparing snapshots
at about 5 year steps can give area-specific conversion rates. Pre-computing
summaries by region or ecozone keeps queries fast.

## Using this repo

Working rules are in [`CLAUDE.md`](CLAUDE.md) and
[`CONTRIBUTING.md`](CONTRIBUTING.md). Run `scripts/bootstrap-repo-settings.sh`
once for branch protection and labels.

## Solo-maintainer auto-merge (optional)

`.github/workflows/` holds two workflows that make the maintainer's own green
PRs merge themselves. `auto-merge.yml` matches the maintainer by login
(`ricschuster`), since the repo is owned by an organization.

- `auto-merge.yml` arms squash auto-merge on PRs opened by the repository
  owner (never on anyone else's, Dependabot included) and brings the PR level
  with `main`.
- `update-branches.yml` updates every armed PR after each push to `main`, so
  strict "up to date" branch protection does not leave them stuck BEHIND.

One-time setup: create a fine-grained personal access token for this repo only
(Contents, Pull requests and Workflows: read/write) and store it as the
`AUTO_MERGE_TOKEN` secret. `GITHUB_TOKEN` cannot be used because GitHub starts
no workflows for pushes or merges made with it, so the PR's checks would never
run on the updated branch. Rotate the PAT before it expires. `ci.yml` already
runs on PRs only: with strict protection every PR is tested against current
`main` before it merges.

## Cache warming (optional)

`.github/workflows-optional/warm-cache.yml` saves a cache from `main`, because
a PR can read caches saved on `main` but not caches saved by another PR. Use it
if a CI job downloads something slow on every run. Move it into
`.github/workflows/`, fill in the two placeholders, and use the same path and
key in the `actions/cache` step of your CI job.

## What's included

- `CLAUDE.md`: working rules and durable context, loaded automatically by
  Claude Code.
- `.claude/settings.json`: default tool permissions for Claude Code sessions
  in this repo.
- `docs/design/`: design notes, starting with a project brief template.
- `docs/decisions/`: Architecture Decision Records (ADRs).
- `docs/handoffs/`: session handoff template for continuity between work
  sessions.
- `.github/`: issue forms, PR template, Dependabot config, a stack-neutral CI
  workflow (docs-only PRs skip stack jobs, one required `checks` status), and
  optional solo-maintainer auto-merge and cache-warming workflows.
- `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`, `LICENSE`.
- `scripts/bootstrap-repo-settings.sh`: one-time repo settings setup (branch
  protection, auto-merge, labels) that a template cannot carry over on its
  own.

## License

GNU General Public License v3.0. Replace with your own choice if different.
