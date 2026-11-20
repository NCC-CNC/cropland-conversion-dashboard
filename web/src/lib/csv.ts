import type { Meta, Summary } from './types';

function esc(v: string | number): string {
  const s = String(v);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function num(v: number | null, digits: number): string {
  return v === null ? '' : v.toFixed(digits);
}

/** Build the CSV for the current summary. One row per interval and class, plus a total row. */
export function buildCsv(summary: Summary, meta: Meta, selectedCells = summary.cellCount): string {
  const header = [
    'area_id',
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
  for (const iv of summary.intervals) {
    for (const r of [...iv.rows, iv.total]) {
      lines.push(
        [
          esc(meta.area_id),
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
  lines.push('');
  lines.push(
    esc(
      'Screening estimate from the AAFC Annual Crop Inventory aggregated to ' +
        `${meta.cell_size_m} m cells. Not parcel level. Source: ${meta.source}`,
    ),
  );
  return lines.join('\n') + '\n';
}
