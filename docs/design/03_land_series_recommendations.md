# 03 Using AAFC Land Use Time Series to improve Annual Crop Inventory accuracy

Status: draft recommendations for discussion, product facts verified
2026-11-26 against the AAFC data product specification. Nothing here is built into the
dashboard. Tracks issue #31. Requested in client feedback of 2026-11-26.

## Purpose

The dashboard treats crop in the Annual Crop Inventory (ACI) as the reliable
signal and reads "natural before, crop now" as conversion. Two weaknesses
remain, both already listed as caveats:

1. The split of conversion by natural class (forest, grassland, wetland,
   shrubland) is indicative, because ACI class labels shift between years.
2. Non-crop labels in ACI are less certain than crop labels, so a cell that
   flips between grassland and wetland can look like change or hide it.

This note proposes how the AAFC Land Use Time Series (LUTS) could reduce both.

## What each product is

Checked on 2026-11-26 against the AAFC Land Use ISO 19131 data product
specification (Revision A) and the Open Canada records for both products.

- ACI: annual 30 m crop and land cover maps, 2009 to 2025 (56 m in 2009 and
  2010). Stated overall accuracy target of at least 85%. Licence: Open
  Government Licence Canada. Not confirmed from the record page: coverage by
  year (Prairies only in 2009 and 2010, whole agricultural extent from 2011)
  and the per-class accuracy; the class list sits in a linked CSV not yet read.
- AAFC Land Use (the note calls it LUTS): 30 m GeoTIFF maps for 2000, 2005,
  2010, 2015 and 2020, each "circa" its year (the 2010 map can represent 2010
  to 2011). Coverage is Canada south of 60 degrees N. Described by the
  specification as a curated meta-analysis of several high-quality datasets,
  built incrementally from consolidated pixel histories with visual checks in
  imagery. Inputs span 1990 to 2021 (the Open Canada record says 2000 to
  2021). Licence: Open Government Licence Canada, no warranty. The
  specification says updates are ongoing, so record the version and download
  date when used.

## What the specification says that affects the recommendations

- Accuracy: no per-class or overall accuracy figures are given for Land Use.
  Thematic accuracy is an as-is disclaimer, and logical consistency and
  positional accuracy are "not defined at this time". No ACI per-class accuracy
  was found either. Per-class accuracy for wetland and grassland remains
  unknown for both products.
- Differencing warning: the specification says that differencing maps is not an
  adequate way to quantify change without an accuracy assessment of the change
  pixels, and that change pixels are always a mix of real change and
  uncertainty. This applies to the dashboard's own method and belongs in its
  caveats.
- Legend: Land Use follows IPCC categories with regional subclasses. Grassland
  and shrubland are merged (regional codes 63 to 69), forest wetland (42) is
  separate from wetland (73 to 79), and cropland (51) is "annual and perennial"
  with no separate pasture and forage class. Newer classes (for example 52 and
  56 from 2015, 55 from 2010) do not exist in early epochs, so full series
  comparison is not possible for them.
- No ACI crosswalk is provided and no minimum mapping unit is stated (30 m
  pixels only).
- Dependence on ACI: ACI 2010 to 2020 is the first listed input, alongside
  other datasets such as GLAD cropland expansion. The share is not quantified.
  The 2000 and 2005 maps predate ACI, so they are more independent for
  baselines. Land Use also carries its own "land converted to cropland"
  classes (55 and 56), which overlap the dashboard's purpose.

## Recommendations, in suggested order

### R1. Take the baseline natural class from LUTS, keep crop from ACI

Use ACI only for the crop signal (where it is strongest). For the "by natural
class" split, assign each converted cell its class from the LUTS epoch nearest
the baseline year. This targets caveat 1 directly: the class split would not
depend on ACI label drift. Lowest effort, easiest to explain. Limit found on
verification: Land Use merges grassland and shrubland, so shrubland could not
be reported separately from this route, and it would need a crosswalk and a
decision on forest wetland.

### R2. Temporal consistency filter on ACI natural classes

Before comparing snapshots, relabel an ACI natural-class pixel when it
disagrees with both neighbouring LUTS epochs and with the ACI mode across
available years. A simple rule set (agree in at least 2 of 3 sources) is
enough to start. The noise filter work in issue #3 is the natural home for this.

### R3. Stable-class mask for wetland and grassland

Where LUTS shows the same natural class at all epochs, treat that pixel as
stable. An ACI flip between wetland and grassland inside a stable LUTS pixel is
reclassified to the LUTS class. Report how many pixels this changes, per area,
as a quality indicator.

### R4. Probabilistic smoothing

If rule based filters are not enough, model each pixel's class history as a
hidden Markov chain with ACI and LUTS as noisy observations and low
probabilities for implausible jumps (for example forest to wetland to forest in
consecutive years). This is more work and harder to explain, so try R1 to R3
first.

### R5. Use LUTS to build validation samples, with care

Draw stratified samples from areas where LUTS and ACI agree for evidence of
stability and from disagreement areas for evidence of error. For the Estevan to
Melita to Russell to Melville test area, compare against independent
imagery interpretation, not LUTS alone. LUTS is partly built from ACI, so
agreement between the two is not independent proof of accuracy.

### R6. Settle the pasture and forage question first

Whether tame pasture and forage count as crop changes results by about 2x
(see the handoff of 2026-11-20). Land Use has no separate pasture and forage class
(cropland 51 includes perennial crops), so it is unlikely to settle this; the
specification does separate managed and unmanaged grassland in its summary
table, which may be worth testing. Decide this before tuning anything
else.

## Risks and constraints

- Circularity: shared inputs make agreement look better than it is (R5).
- Epoch mismatch: LUTS epochs (2000, 2005, 2010, 2015, 2020) do not line up
  with every ACI snapshot year, and ACI starts in 2009. Pre-2009 baselines have
  only LUTS to rely on.
- Legend crosswalk: class definitions differ. A written crosswalk table is a
  prerequisite for R1 to R4.
- Scope: LUTS is an AAFC source, so this is inside the stated source scope, but
  adding it to the dashboard still needs an ADR (data contract change).
- Provenance: any filtered output must record rules and versions in the
  methods report so results stay replicable.

## Suggested evaluation

On the v2 test area (issue #30), produce raw ACI-only results and results with
R1, then R1 to R3. Compare totals, class split, and the number of pixels changed
per rule. Judge against an independent sample, not against LUTS.

## Sources consulted

- AAFC Land Use dataset record on Open Canada:
  <https://open.canada.ca/data/en/dataset/fa84a70f-03ad-4946-b0f8-a3b481dd5248>
- AAFC Annual Crop Inventory record:
  <https://open.canada.ca/data/en/dataset/ba2645d5-4458-414d-b196-6303ac06c1c9>
- Earth Engine catalog entry for AAFC ACI:
  <https://developers.google.com/earth-engine/datasets/catalog/AAFC_ACI>
- AAFC Land Use ISO 19131 Data Product Specification, Revision A:
  <https://agriculture.canada.ca/atlas/data_donnees/landuse/supportdocument_documentdesupport/en/ISO_19131_AAFC_Land_Use_Data_Product_Specification.pdf>
- Huffman et al., integration of Canadian land use datasets (EARSeL 2015).
