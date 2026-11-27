import { describe, expect, it } from 'vitest';
import { buildReportDoc } from './report';
import { reportDocx } from './reportDocx';
import type { Meta, PolygonGeometry } from './types';

const meta = {
  name: 'Test', area_id: 't', generated: '2026-11-26', cell_size_m: 1000, snapshots: [2011, 2025],
  method: 'm', source: 's', caveats: ['c'], intervals: [{ from: 2011, to: 2025, years: 14 }],
} as unknown as Meta;
const poly: PolygonGeometry = { type: 'Polygon', coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] };
const input = { summaries: [{ target: 'crop', cellCount: 1, intervals: [] }], meta, poly, areaKm2: 1, url: 'u', generatedAt: 'now' } as never;

describe('reportDocx', () => {
  it('builds a docx (zip) file', async () => {
    const blob = await reportDocx(input);
    const head = new Uint8Array(await blob.arrayBuffer()).slice(0, 2);
    expect(String.fromCharCode(...head)).toBe('PK');
    expect(blob.size).toBeGreaterThan(1000);
  });
  it('model has the main sections', () => {
    const heads = buildReportDoc(input).filter((b) => b.t === 'h').map((b) => (b as { text: string }).text);
    expect(heads).toEqual(expect.arrayContaining(['Selection', 'Summary statistics', 'Methods', 'Caveats', 'Data source']));
  });
});
