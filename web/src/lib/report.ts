import { cap, fmtHa, fmtPct } from './format';
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
  summary: Summary;
  meta: Meta;
  poly: PolygonGeometry;
  areaKm2: number;
  /** Link that reopens this selection. */
  url: string;
  /** ISO timestamp for when the report was made. */
  generatedAt: string;
}

/** Markdown overview: methods, caveats, selection coordinates and summary statistics. */
export function buildReport(r: ReportInput): string {
  const { summary, meta, poly } = r;
  const out: string[] = [];
  out.push('# Cropland conversion summary', '');
  out.push(`Study area: ${meta.name} (${meta.area_id})`);
  out.push(`Report generated: ${r.generatedAt}`);
  out.push(`Data generated: ${meta.generated}`);
  out.push(`Link to reopen this selection: ${r.url}`, '');

  out.push('## Selection', '');
  out.push(`- Selected area: ${r.areaKm2.toLocaleString('en-CA', { maximumFractionDigits: 1 })} km2`);
  out.push(`- Grid cells counted: ${summary.cellCount} (cell size ${meta.cell_size_m} m)`);
  out.push('- Coordinate system: WGS84, latitude then longitude, in degrees');
  out.push(`- Vertices (${polygonVertices(poly).length}, in order, outer ring):`, '');
  out.push('```', coordinatesText(poly), '```', '');
  out.push('GeoJSON geometry:', '', '```json', JSON.stringify({ type: 'Polygon', coordinates: [polygonCoords(poly)] }), '```', '');

  out.push('## Summary statistics', '');
  for (const iv of summary.intervals) {
    out.push(`### ${iv.from} to ${iv.to} (${iv.years} years)`, '');
    out.push('| Class | Natural ha, baseline | Converted ha | Share converted | ha per year |');
    out.push('| --- | ---: | ---: | ---: | ---: |');
    for (const row of [...iv.rows, iv.total]) {
      out.push(
        `| ${cap(row.cls)} | ${fmtHa(row.naturalHa)} | ${fmtHa(row.convertedHa)} | ${fmtPct(row.percent)} | ${fmtHa(row.ratePerYear)} |`,
      );
    }
    out.push('');
  }
  out.push('Share converted is the percent of baseline natural hectares that were crop in the later year. Class split is indicative; the total is the more reliable figure.', '');

  out.push('## Methods', '', meta.method, '');
  out.push(`Snapshots used: ${meta.snapshots.join(', ')}`);
  out.push(`A cell is counted when its centre falls inside the selected shape. Hectares are rounded and approximate.`, '');
  out.push('## Caveats', '');
  out.push('- This is a screening tool, not a parcel-level or legal record.');
  for (const c of meta.caveats) out.push(`- ${c}`);
  out.push('', '## Data source', '', meta.source, '');
  return out.join('\n');
}

function polygonCoords(poly: PolygonGeometry): number[][] {
  const v = polygonVertices(poly).map((p) => [p.lon, p.lat]);
  return v.length ? [...v, v[0]] : v;
}
