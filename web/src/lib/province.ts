import type { Coverage, Interval, ProvinceSummary } from './types';

export interface ProvinceRow {
  target: string;
  convertedHa: number;
  percent: number | null;
}

export interface ProvinceIntervalView {
  key: string;
  from: number;
  to: number;
  years: number;
  naturalHa: number;
  rows: ProvinceRow[];
}

export interface ProvinceCardModel {
  code: string;
  name: string;
  /** True only when the summary says every farming-zone region is covered. */
  provincial: boolean;
  /** Short heading, never "total" for partial coverage. */
  heading: string;
  /** One or two plain sentences on what the figures cover. */
  coverageText: string;
  /** Region ids with data, for detail on request. */
  regionsRun: string[];
  intervals: ProvinceIntervalView[];
}

/** Province codes present in the summary, in a fixed order (all last). */
export function provinceCodes(s: ProvinceSummary): string[] {
  return ['MB', 'SK', 'all'].filter((c) => s.provinces[c]);
}

const pct = (f: number) => `${(f * 100).toFixed(1)}%`;

/** Region name with its province, taken from an id such as "aspen-parkland-mb". */
function withProvince(id: string, name: string): string {
  const m = /-(mb|sk)$/.exec(id);
  return m ? `${name} (${m[1].toUpperCase()})` : name;
}

/** Plain wording for a coverage block. Provincial wording is allowed only when `complete` is true. */
export function coverageSentence(
  name: string,
  cov: Coverage,
  covered: string[] = [],
  partial: string[] = [],
): string {
  if (cov.complete) {
    return `All ${cov.regions_total} farming-zone regions are covered, so these figures are the ${name} total for the farming zone.`;
  }
  const list = (xs: string[]) => xs.join(', ');
  const done = covered.length > 0 ? ` Covered regions: ${list(covered)}.` : '';
  const part =
    partial.length > 0
      ? ` Partly covered regions (the data holds only part of the region, or the Annual Crop Inventory maps little of it in the latest year or a baseline year): ${list(partial)}.`
      : '';
  return `Partial coverage: ${cov.regions_covered.length} of ${cov.regions_total} farming-zone regions are covered, and about ${pct(cov.fraction)} of the farming-zone area has data. These figures describe only that data and are not a ${name} total.${done}${part}`;
}

/**
 * Build the card model for one province code. Returns null if the code is absent. `regionName` maps a
 * region id to a display name. The heading says "total" only when coverage is complete.
 */
export function buildProvinceCard(
  s: ProvinceSummary,
  code: string,
  regionName: (id: string) => string = (id) => id,
): ProvinceCardModel | null {
  const p = s.provinces[code];
  if (!p) return null;
  const cov = p.coverage;
  const provincial = cov.complete === true;
  const name = code === 'all' ? 'Manitoba and Saskatchewan' : p.name;
  const ivs: Interval[] = s.years.intervals;
  const intervals = ivs.flatMap((iv): ProvinceIntervalView[] => {
    const key = `${iv.from}-${iv.to}`;
    const d = p.intervals[key];
    if (!d) return [];
    return [
      {
        key,
        from: iv.from,
        to: iv.to,
        years: iv.years,
        naturalHa: d.total.natural_ha,
        rows: s.targets.map((t) => ({
          target: t,
          convertedHa: d.total.converted_ha[t] ?? 0,
          percent: d.total.converted_pct[t] ?? null,
        })),
      },
    ];
  });
  const regionsRun = p.regions.filter((r) => cov.regions_run.includes(r));
  return {
    code,
    name,
    provincial,
    heading: provincial ? `${name} total` : `${name}: covered regions only`,
    coverageText: coverageSentence(
      name,
      cov,
      p.regions.filter((r) => cov.regions_covered.includes(r)).map((r) => withProvince(r, regionName(r))),
      p.regions.filter((r) => (cov.regions_partial ?? []).includes(r)).map((r) => withProvince(r, regionName(r))),
    ),
    regionsRun,
    intervals,
  };
}
