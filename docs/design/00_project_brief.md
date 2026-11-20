# 00 Project Brief

## What this is

Cropland Conversion Dashboard is a web tool that summarizes land conversion to
cropland for any area a user selects, using the AAFC Annual Crop Inventory.

It is a screening and communication tool for conservation planning and grant
justification, not a legal or parcel-level record. The goal is to let a user
go to a site, select an area, and see what has changed, or at least receive a
basic summary, in seconds.

## Who it is for

- Conservation practitioners and planners who need rates of land conversion
  for grant applications and project justification, often monthly.
- Partners and researchers who now rely on coarse regional reports (for
  example joint venture reports) or one-off study results.

Assumes no GIS expertise: draw or click an area, read the summary.

## The core idea (one screen)

The Annual Crop Inventory maps crop types annually with reported accuracy
above 90%. Download snapshots at roughly 5 year increments. For a selected
area, compare each earlier snapshot to the most recent one: cells that are
crop now but were forest, grassland, or wetland (or other non-crop) before are
conversions. The dashboard reports hectares and percent of natural habitat
converted over each interval, with the rate per year.

Because full rasters are large, work is done up front: pre-compute transition
counts by region or ecozone (and tile or index them) so a user query only sums
pre-aggregated cells.

## MVP scope

1. Pipeline to download Crop Inventory snapshots and harmonize classes
   (natural: forest, grassland, wetland; crop; other) for one ecozone.
2. Pre-computed transition summaries between snapshots.
3. Web map where a user draws a polygon and gets hectares, percent, and
   annual rate of conversion by natural class, with a CSV export.

## Explicit non-goals (for now)

- Producing a new land cover product; we reuse AAFC's.
- Attributing causes of conversion or predicting future conversion.
- Legal or parcel-level accuracy claims.

## Design principles

1. Precompute, do not scan: interactivity depends on summarizing before the
   user asks.
2. Be honest about accuracy: state crop-class accuracy, class changes over the
   series, and that small areas carry more uncertainty.
3. Start regional (one ecozone), prove the method, then scale.

## Open questions

- Which snapshot years to use, and how to handle early years with partial
  national coverage and changing class schemes.
- How to separate real conversion from classification noise (for example
  minimum change thresholds or majority filters).
- Where to host pre-computed data and the web app.
- Validation source for conversion rates (existing regional analyses).
