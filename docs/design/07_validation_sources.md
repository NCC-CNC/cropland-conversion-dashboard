# Validation sources for conversion rates (issue #6)

Status: desk review only. No independent analysis has been obtained or
reproduced, and permission to use any partner results has not been confirmed.
Issue #6 stays open until the owner confirms sources and permissions.

## Published benchmarks found (2026-11-27)

|Source|What it says|Comparable to the dashboard?|
|---|---|---|
|NCC statements reported by The Weather Network, and a Grassland Conservation Initiative document by DUC, NCC and the Canadian Cattle Association|About 60,000 ha (148,000 acres) of native prairie lost per year across the three Prairie provinces|Roughly. All grassland loss in AB, SK and MB, not only crop, and the basis is not given in the sources seen|
|CAPI Quick Think on the 2021 Census of Agriculture|Natural pasture fell from 35.2 M to 33.9 M acres from 2011 to 2021 (about 53,000 ha per year, Canada), largest losses in Alberta|Loosely. Farm-reported land use, not mapped cover change, and it includes the net effect of regrowth|
|Statistics Canada, Canadian Agriculture at a Glance|Manitoba natural pasture was 19.1 percent of farm area in 2021, down 3.3 percent from 2016|Direction only|
|AAFC agricultural land use indicator|Canada natural pasture rose 0.6 percent from 2016 to 2021|Conflicts with the longer trend, which shows how noisy census land use is|
|WWF Plowprint reports (2016 to 2024)|About 1.9 M acres a year converted across the US and Canadian Great Plains, built on the same ACI for Canada, with a two sequential year rule to count a pixel as crop|Same data family and a similar persistence rule, but one number for the whole Great Plains|

## Dashboard rates for the same question

From the published `mb-sk-farming-zone` province summary (MB and SK farming zone
only, about 79 percent of that area covered, Alberta not included), natural
habitat converted to crop, in hectares per year:

|Interval|All natural classes|Grassland only|
|---|---|---|
|2011 to 2025|53,200|25,500|
|2016 to 2025|26,000|16,100|
|2021 to 2025|18,200|11,000|

## Reading the comparison

- The dashboard grassland rate (about 16,000 to 25,000 ha per year for MB and SK)
  is lower than the 60,000 ha per year quoted for three provinces. It is the
  right order of magnitude once Alberta, non-crop conversion and partial
  coverage are taken into account, but this is a rough plausibility check, not a
  validation.
- The dashboard is expected to read low: it needs two sequential crop years
  (persistence), removes patches under 0.5 ha, and excludes cells that were
  crop, pasture or urban in an earlier snapshot.
- The interval rates fall as the baseline year moves forward, which fits the
  reported slowdown, but the 2011 baseline is unreliable (see the 2011 caution).
- None of these sources reports mapped conversion by ecoregion, so they cannot
  validate the regional figures.

## What would count as validation

- A regional analysis with a stated method, such as a partner or contractor
  conversion layer for part of the Prairies, compared cell by cell.
- Field or imagery checks of a sample of converted patches, for example from the
  30 m layer, with the share confirmed on high resolution imagery.

## For the owner

- Say which partner or published regional analyses can be used, and confirm
  permission.
- Decide whether a sample check of converted patches on imagery is wanted.
- Primary sources behind the NCC and Weather Network figure should be located
  before it is quoted in a grant.
