# 01 Feasibility Spike Design

Status: draft for review. Covers GitHub issues #1, #2, #3 and #6.

## Goal

Prove the method on one ecozone: download Annual Crop Inventory (ACI)
snapshots, harmonize classes, build a transition matrix, and check the
resulting conversion rates against independent estimates. Output is a go or
no-go on the method, not a product.

## What we know about the data

From the AAFC ACI metadata and the Earth Engine catalog (verify against the
AAFC source before relying on any of this):

- Annual maps start in 2009. 2009 and 2010 are 56 m and cover mainly the
  Prairie Provinces. National expansion began in 2011, at 30 m.
- Earth Engine lists coverage through 2024. Check what AAFC has published
  since.
- Legend codes: water 20, urban 34, shrubland 50, wetland 80, forest 210-230
  (conifer, broadleaf, mixedwood), crop classes in the 120s to 200s. Code 120
  is generic agriculture and appears where ground data were missing (for
  example British Columbia in 2021).
- Licence is OGL-Canada-2.0, so redistribution of derived summaries is fine.

## Decision 1: spike ecozone (#1)

Recommendation: Prairies ecozone, limited to one or two ecoprovinces (for
example Parkland or Central Grassland) to keep raster volume manageable.

Why: conversion of grassland and wetland to crop is the central story, ACI
coverage is best there, and published estimates exist for validation. The
Mixedwood Plains is the alternative (strong recent literature, smaller area)
but has little native grassland left, so it tests the method less.

## Decision 2: snapshot years (#2)

Recommendation: 2011, 2016, 2021 and the latest complete year. All are 30 m
and national in coverage, giving roughly 5 year intervals. Treat 2009 and
2010 as out of scope for the headline numbers: they are 56 m and
Prairie-only, so cells are not comparable to later years without resampling.

Class harmonization: map ACI codes to three groups, natural (forest,
grassland, wetland, shrubland), crop, and other (water, urban, barren,
cloud). Record any legend changes between years in a lookup table under
version control.

Known limit to state in the UI: ACI crop classes include perennial forage and
pasture. Conversion from native grassland to tame pasture is not "crop" in
the annual sense, and the two cannot be separated from ACI alone.

## Decision 3: separating conversion from noise (#3)

A single-year class flip is often classification error, not conversion.
Planned approach, tested as a sensitivity analysis rather than fixed up front:

1. Require persistence: a cell counts as converted only if it is crop in the
   target snapshot and in the one before it (or in a multi-year composite),
   and natural in the baseline snapshot and one adjacent year.
2. Apply a minimum patch size (for example 0.5 ha) and a majority filter.
3. Report results at several threshold settings and show the spread.

Pick the default from how well results line up with validation sources.

## Validation (#6)

Candidate sources to confirm and obtain (not yet checked):

- Fyson, Wilmshurst and Callaghan, FACETS 2024, land change in the Mixedwood
  Plains 2011-2022.
- Statistics Canada ecosystem accounts (Accounting for ecosystem change in
  Canada, Catalogue 16-201-X).
- AAFC 2026 report on drivers of agricultural land change (publications.gc.ca,
  A59-123-2026).
- Joint venture and Ducks Unlimited Canada prairie conversion reports.

Method: compare our hectares per year for matching ecozone and years. A
difference is expected where definitions differ, so log the definitions of
each source next to the numbers.

## Spike steps

1. Choose ecoprovince and fix the boundary file (Ecological Framework of
   Canada).
2. Download the four snapshots and clip to the boundary.
3. Harmonize classes and verify cell alignment and projection.
4. Compute transition matrices per interval, with and without the noise
   filters.
5. Compare with validation sources and write up in a handoff note.
6. Time a polygon query against the summaries to check the precompute idea.

## Success criteria

- Method runs end to end for one ecoprovince in under a day of compute.
- Conversion estimates are within a plausible range of at least one
  independent source, with differences explained.
- A polygon query over pre-aggregated data returns in under a second.

## Out of scope

Stack choice (#4) and the web map (#5). The spike can use any tooling.
