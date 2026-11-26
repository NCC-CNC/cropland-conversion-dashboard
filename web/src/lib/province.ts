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

/** Plain wording for a coverage block. Provincial wording is allowed only when `complete` is true. */
export function coverageSentence(name: string, cov: Coverage, regionNames: string[]): string {
  if (cov.complete) {
    return `All ${cov.regions_total} farming-zone regions are covered, so these figures are the ${name} total for the farming zone.`;
  }
  const run = regionNames.length > 0 ? ` Regions covered by this data: ${regionNames.join(', ')}.` : '';
  return `Partial coverage: ${cov.regions_run.length} of ${cov.regions_total} farming-zone regions have data, about ${pct(cov.fraction)} of the farming-zone area. These figures describe only that data and are not a ${name} total.${run}`;
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
    coverageText: coverageSentence(name, cov, regionsRun.map(regionName)),
    regionsRun,
    intervals,
  };
}
