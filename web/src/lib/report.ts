import { cap, fmtHa, fmtPct } from './format';
import { intervalNote } from './intervals';
import { targetCaveats, targetLabel } from './targets';
import type { Meta, PolygonGeometry, Summary } from './types';

const COORD_DECIMALS = 5; // about 1 m

export interface Vertex {
  lon: number;
  lat: number;
}

/** Vertices of the outer ring in order, without the repeated closing point. */
export function polygonVertices(poly: PolygonGeometry): Vertex[] {
  const ring = poly.coordinates[0] ?? [];
  const open = ring.length > 1 && ring[0][0] === ring[ring.length - 1][0] && ring[0][1] === ring[ring.length - 1][1]
    ? ring.slice(0, -1)
    : ring;
  return open.map(([lon, lat]) => ({
    lon: Number(lon.toFixed(COORD_DECIMALS)),
    lat: Number(lat.toFixed(COORD_DECIMALS)),
  }));
}

/** Plain text, one "lat, lon" line per vertex (WGS84), easy to paste into a methods section. */
export function coordinatesText(poly: PolygonGeometry): string {
  return polygonVertices(poly)
    .map((v, i) => `${i + 1}. ${v.lat.toFixed(COORD_DECIMALS)}, ${v.lon.toFixed(COORD_DECIMALS)}`)
    .join('\n');
}

export interface ReportInput {
  /** One summary per target, in target order (see summarizeTargets). */
  summaries: Summary[];
  meta: Meta;
  poly: PolygonGeometry;
  areaKm2: number;
  /** Link that reopens this selection. */
  url: string;
  /** ISO timestamp for when the report was made. */
  generatedAt: string;
}

/** Format-neutral report content, rendered to Word (docx) or to Markdown. */
export type ReportBlock =
  | { t: 'h'; level: 1 | 2 | 3 | 4; text: string }
  | { t: 'p'; text: string; boldLead?: string }
  | { t: 'ul'; items: string[] }
  | { t: 'table'; head: string[]; rows: string[][]; right: number[] }
  | { t: 'code'; text: string };

/** The report: methods, caveats, selection coordinates and summary statistics. */
export function buildReportDoc(r: ReportInput): ReportBlock[] {
  const { summaries, meta, poly } = r;
  const summary = summaries[0];
  const out: ReportBlock[] = [];
  const h = (level: 1 | 2 | 3 | 4, text: string) => out.push({ t: 'h', level, text });
  const p = (text: string, boldLead?: string) => out.push({ t: 'p', text, boldLead });
  h(1, 'Cropland conversion summary');
  p(`Study area: ${meta.name} (${meta.area_id})`);
  p(`Report generated: ${r.generatedAt}`);
  p(`Data generated: ${meta.generated}`);
  p(`Link to reopen this selection: ${r.url}`);

  h(2, 'Selection');
  out.push({
    t: 'ul',
    items: [
      `Selected area: ${r.areaKm2.toLocaleString('en-CA', { maximumFractionDigits: 1 })} km2`,
      `Grid cells counted: ${summary.cellCount} (cell size ${meta.cell_size_m} m)`,
      'Coordinate system: WGS84, latitude then longitude, in degrees',
    ],
  });
  p(`Vertices (${polygonVertices(poly).length}, in order, outer ring):`);
  out.push({ t: 'code', text: coordinatesText(poly) });
  p('GeoJSON geometry:');
  out.push({ t: 'code', text: JSON.stringify({ type: 'Polygon', coordinates: [polygonCoords(poly)] }) });

  h(2, 'Summary statistics');
  const multi = summaries.length > 1;
  const caveats = targetCaveats(meta);
  summaries[0].intervals.forEach((first, k) => {
    h(3, `${first.from} to ${first.to} (${first.years} years)`);
    const ivNote = intervalNote(meta, first.from, first.to);
    if (ivNote) p(ivNote, 'Caution: ');
    for (const s of summaries) {
      const iv = s.intervals[k];
      if (multi) h(4, `Natural habitat converted to ${targetLabel(s.target)}`);
      out.push({
        t: 'table',
        head: ['Target', 'Class', 'Natural ha, baseline', 'Converted ha', 'Share converted', 'ha per year'],
        right: [2, 3, 4, 5],
        rows: [...iv.rows, iv.total].map((row) => [
          cap(s.target),
          cap(row.cls),
          fmtHa(row.naturalHa),
          fmtHa(row.convertedHa),
          fmtPct(row.percent),
          fmtHa(row.ratePerYear),
        ]),
      });
      if (caveats[s.target]) p(caveats[s.target], 'Lower confidence: ');
    }
  });
  p(
    'Share converted is the percent of baseline natural hectares that were converted to the target class in the later year. A cell counts in one target only, and targets are reported separately, never added together. Class split is indicative; the total is the more reliable figure.',
  );

  h(2, 'Methods');
  p(meta.method);
  p(`Snapshots used: ${meta.snapshots.join(', ')}`);
  p('A cell is counted when its centre falls inside the selected shape. Hectares are rounded and approximate.');
  h(2, 'Caveats');
  const items = ['This is a screening tool, not a parcel-level or legal record.'];
  // Target caveats already appear under their tables above.
  const shown = new Set(Object.values(caveats));
  for (const c of meta.caveats) if (!shown.has(c)) items.push(c);
  out.push({ t: 'ul', items });
  h(2, 'Data source');
  p(meta.source);
  return out;
}

/** Markdown rendering of the report (plain text view, used in tests). */
export function buildReport(r: ReportInput): string {
  const lines: string[] = [];
  for (const b of buildReportDoc(r)) {
    if (b.t === 'h') lines.push(`${'#'.repeat(b.level)} ${b.text}`, '');
    else if (b.t === 'p') lines.push(b.boldLead ? `**${b.boldLead.trim()}** ${b.text}` : b.text, '');
    else if (b.t === 'ul') lines.push(...b.items.map((i) => `- ${i}`), '');
    else if (b.t === 'code') lines.push('```', b.text, '```', '');
    else {
      lines.push(`| ${b.head.join(' | ')} |`);
      lines.push(`| ${b.head.map((_, i) => (b.right.includes(i) ? '---:' : '---')).join(' | ')} |`);
      for (const row of b.rows) lines.push(`| ${row.join(' | ')} |`);
      lines.push('');
    }
  }
  return lines.join('\n');
}

function polygonCoords(poly: PolygonGeometry): number[][] {
  const v = polygonVertices(poly).map((p) => [p.lon, p.lat]);
  return v.length ? [...v, v[0]] : v;
}
