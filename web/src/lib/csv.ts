import { targetCaveats } from './targets';
import type { Meta, Summary } from './types';

function esc(v: string | number): string {
  const s = String(v);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function num(v: number | null, digits: number): string {
  return v === null ? '' : v.toFixed(digits);
}

/**
 * Build the CSV from one summary per target. One row per target, interval and class, plus a total
 * row for each target and interval. Targets are never added together.
 */
export function buildCsv(summaries: Summary[], meta: Meta, selectedCells = summaries[0]?.cellCount ?? 0): string {
  const header = [
    'area_id',
    'target',
    'baseline_year',
    'latest_year',
    'class',
    'natural_ha_baseline',
    'converted_ha',
    'percent_converted',
    'annual_rate_ha_per_year',
    'cells_in_selection',
  ];
  const lines = [header.join(',')];
  for (const summary of summaries) {
    for (const iv of summary.intervals) {
      for (const r of [...iv.rows, iv.total]) {
        lines.push(
          [
            esc(meta.area_id),
            esc(summary.target),
            iv.from,
            iv.to,
            r.cls,
            num(r.naturalHa, 2),
            num(r.convertedHa, 2),
            num(r.percent, 2),
            num(r.ratePerYear, 2),
            selectedCells,
          ].join(','),
        );
      }
    }
  }
  lines.push('');
  const caveats = targetCaveats(meta);
  for (const iv of meta.intervals) {
    if (iv.note) lines.push(esc(`Caution for ${iv.from} to ${iv.to}: ${iv.note}`));
  }
  for (const s of summaries) {
    if (caveats[s.target]) lines.push(esc(`Note on ${s.target}: ${caveats[s.target]}`));
  }
  lines.push(
    esc(
      'Screening estimate from the AAFC Annual Crop Inventory aggregated to ' +
        `${meta.cell_size_m} m cells. Not parcel level. Source: ${meta.source}`,
    ),
  );
  return lines.join('\n') + '\n';
}
