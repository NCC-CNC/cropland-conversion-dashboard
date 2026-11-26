# 03 Using AAFC Land Use Time Series to improve Annual Crop Inventory accuracy

Status: draft recommendations for discussion. Nothing here is built into the
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

## What each product is (as understood, to be verified)

- ACI: annual 30 m crop and land cover maps. Started in 2009 on the Prairies
  (56 m in 2009 and 2010), whole agricultural extent from 2011. Stated overall
  accuracy target of at least 85%. Includes wetland, grassland, shrubland,
  peatland and pasture and forage classes.
- LUTS: 30 m land use at 5 year steps (published services for 2000, 2005,
  2010, 2015, 2020), described by AAFC as a curated meta-analysis of several
  high-quality datasets built with an incremental, pixel-history approach that
  uses imagery checks.

Not yet confirmed from the data product specification (ISO 19131) and to check
before relying on any recommendation below: per-class accuracy for wetland and
grassland in either product, the LUTS class legend and minimum mapping unit,
how much of LUTS is itself derived from ACI, and licence terms.

## Recommendations, in suggested order

### R1. Take the baseline natural class from LUTS, keep crop from ACI

Use ACI only for the crop signal (where it is strongest). For the "by natural
class" split, assign each converted cell its class from the LUTS epoch nearest
the baseline year. This targets caveat 1 directly: the class split would not
depend on ACI label drift. Lowest effort, easiest to explain.

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
(see the handoff of 2026-11-20). LUTS land use categories may help separate
cultivated forage from native grassland. Decide this before tuning anything
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
  https://ouvert.canada.ca/data/dataset/fa84a70f-03ad-4946-b0f8-a3b481dd5248
- AAFC Annual Crop Inventory record:
  https://open.canada.ca/data/en/dataset/ba2645d5-4458-414d-b196-6303ac06c1c9
- Earth Engine catalog entry for AAFC ACI:
  https://developers.google.com/earth-engine/datasets/catalog/AAFC_ACI
- Huffman et al., integration of Canadian land use datasets (EARSeL 2015).
