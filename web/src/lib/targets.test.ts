import { describe, expect, it } from 'vitest';
import { buildCsv } from './csv';
import { normaliseCells } from './data';
import { buildGrid } from './grid';
import { buildReport } from './report';
import { summarize, summarizeTargets } from './summary';
import { metaTargets, targetCaveats } from './targets';
import type { Meta, PolygonGeometry, RawCells } from './types';

// Cells 0..3. Nested form with all-zero arrays left out, as the pipeline writes it:
// pasture has forest only, urban is absent from the interval, barren has nothing.
const nested: RawCells = {
  lon: [0, 1, 0, 1],
  lat: [0, 0, 1, 1],
  area_ha: [100, 100, 100, 100],
  intervals: {
    '2011-2021': {
      natural_ha: { forest: [10, 20, 30, 40], grassland: [5, 5, 5, 5] },
      converted_ha: {
        crop: { forest: [1, 2, 3, 4], grassland: [0, 0, 1, 1] },
        pasture: { forest: [0, 5, 0, 0] },
      },
    },
  },
};

const flat: RawCells = {
  ...nested,
  intervals: {
    '2011-2021': {
      natural_ha: nested.intervals['2011-2021'].natural_ha,
      converted_ha: { forest: [1, 2, 3, 4], grassland: [0, 0, 1, 1] },
    },
  },
};

const PASTURE_CAVEAT = 'Pasture caveat text from the pipeline.';
const URBAN_CAVEAT = 'Urban caveat text from the pipeline.';

const baseMeta: Meta = {
  area_id: 'tiny',
  name: 'Tiny',
  bbox: [-1, -1, 2, 2],
  cell_size_m: 1000,
  snapshots: [2011, 2021],
  latest: 2021,
  natural_classes: ['forest', 'grassland'],
  intervals: [{ from: 2011, to: 2021, years: 10 }],
  method: 'm',
  source: 'src',
  generated: '2026-01-01',
  caveats: ['general one', 'general two', PASTURE_CAVEAT, URBAN_CAVEAT],
};
const multiMeta: Meta = { ...baseMeta, targets: ['crop', 'pasture', 'urban'], contract_version: 2 };

const ring: PolygonGeometry = {
  type: 'Polygon',
  coordinates: [[[-0.5, -0.5], [1.5, -0.5], [1.5, 0.5], [-0.5, 0.5], [-0.5, -0.5]]],
};

describe('normaliseCells', () => {
  it('wraps the flat form under crop', () => {
    const c = normaliseCells(flat);
    expect(Object.keys(c.intervals['2011-2021'].converted_ha)).toEqual(['crop']);
    expect(c.intervals['2011-2021'].converted_ha.crop.forest).toEqual([1, 2, 3, 4]);
  });

  it('leaves the nested form unchanged', () => {
    const c = normaliseCells(nested);
    expect(c.intervals['2011-2021'].converted_ha).toEqual(nested.intervals['2011-2021'].converted_ha);
  });

  it('gives the same crop numbers for both formats', () => {
    const a = summarize(normaliseCells(flat), baseMeta, [0, 1]);
    const b = summarize(normaliseCells(nested), multiMeta, [0, 1]);
    expect(b.intervals[0].total).toEqual(a.intervals[0].total);
  });

  it('keeps the arrays, lon, lat and area unchanged', () => {
    const c = normaliseCells(flat);
    expect(c.lon).toEqual(flat.lon);
    expect(c.intervals['2011-2021'].natural_ha).toBe(flat.intervals['2011-2021'].natural_ha);
  });
});

describe('metaTargets', () => {
  it('treats a missing targets list as crop only', () => {
    expect(metaTargets(baseMeta)).toEqual(['crop']);
    expect(metaTargets({ targets: [] })).toEqual(['crop']);
    expect(metaTargets(multiMeta)).toEqual(['crop', 'pasture', 'urban']);
  });
});

describe('summarize per target', () => {
  const cells = normaliseCells(nested);

  it('defaults to crop', () => {
    const s = summarize(cells, multiMeta, [0, 1]);
    expect(s.target).toBe('crop');
    expect(s.intervals[0].total.convertedHa).toBe(3);
  });

  it('sums the active target by class, with a missing class as zero', () => {
    const s = summarize(cells, multiMeta, [0, 1], 'pasture');
    const iv = s.intervals[0];
    expect(iv.rows[0]).toMatchObject({ cls: 'forest', naturalHa: 30, convertedHa: 5 });
    expect(iv.rows[1]).toMatchObject({ cls: 'grassland', naturalHa: 10, convertedHa: 0 });
    expect(iv.total.convertedHa).toBe(5);
    expect(iv.total.percent).toBeCloseTo(12.5, 10);
  });

  it('returns a total for every target, whichever is active, and no combined total', () => {
    for (const active of ['crop', 'pasture', 'urban']) {
      const t = summarize(cells, multiMeta, [0, 1], active).intervals[0].targetTotals;
      expect(Object.keys(t)).toEqual(['crop', 'pasture', 'urban']);
      expect(t.crop.convertedHa).toBe(3);
      expect(t.pasture.convertedHa).toBe(5);
      expect(t.urban.convertedHa).toBe(0);
      expect(t.urban.percent).toBeCloseTo(0, 10);
    }
  });

  it('an unknown target sums to zero', () => {
    expect(summarize(cells, multiMeta, [0, 1], 'barren').intervals[0].total.convertedHa).toBe(0);
  });

  it('a crop only area has only a crop total', () => {
    const s = summarize(normaliseCells(flat), baseMeta, [0, 1]);
    expect(Object.keys(s.intervals[0].targetTotals)).toEqual(['crop']);
  });

  it('summarizeTargets returns one summary per target in order', () => {
    const all = summarizeTargets(cells, multiMeta, [0, 1]);
    expect(all.map((s) => s.target)).toEqual(['crop', 'pasture', 'urban']);
  });
});

describe('buildGrid target shading', () => {
  const cells = normaliseCells(nested);
  it('uses the active target', () => {
    const crop = buildGrid(cells, multiMeta).data.features.map((f) => f.properties?.conv);
    const pasture = buildGrid(cells, multiMeta, 'pasture').data.features.map((f) => f.properties?.conv);
    expect(crop).toEqual([1, 2, 4, 5]);
    expect(pasture).toEqual([0, 5, 0, 0]);
  });
});

describe('targetCaveats', () => {
  it('maps the trailing caveats onto the lower-confidence targets in order', () => {
    expect(targetCaveats(multiMeta)).toEqual({ pasture: PASTURE_CAVEAT, urban: URBAN_CAVEAT });
  });
  it('prefers the keyed target_caveats, even with extra trailing caveats', () => {
    const keyed = {
      ...multiMeta,
      caveats: [...multiMeta.caveats, 'extra area caveat'],
      target_caveats: { urban: URBAN_CAVEAT, pasture: PASTURE_CAVEAT },
    };
    expect(targetCaveats(keyed)).toEqual({ pasture: PASTURE_CAVEAT, urban: URBAN_CAVEAT });
  });
  it('is empty for a crop only area', () => {
    expect(targetCaveats(baseMeta)).toEqual({});
  });
});

describe('buildCsv with targets', () => {
  const cells = normaliseCells(nested);
  const csv = buildCsv(summarizeTargets(cells, multiMeta, [0, 1]), multiMeta);
  const lines = csv.trim().split('\n');

  it('has a target column and rows for every target', () => {
    expect(lines[0].split(',')[1]).toBe('target');
    expect(lines).toContain('tiny,crop,2011,2021,total,40.00,3.00,7.50,0.30,2');
    expect(lines).toContain('tiny,pasture,2011,2021,forest,30.00,5.00,16.67,0.50,2');
    expect(lines).toContain('tiny,urban,2011,2021,total,40.00,0.00,0.00,0.00,2');
  });

  it('has no row that combines targets', () => {
    expect(lines.filter((l) => /^tiny,(all|combined|total),/.test(l))).toHaveLength(0);
    // 3 targets x (2 classes + total) rows, plus the header.
    expect(lines.filter((l) => l.startsWith('tiny,'))).toHaveLength(9);
  });

  it('carries the pipeline caveats for lower-confidence targets only', () => {
    expect(csv).toContain(PASTURE_CAVEAT);
    expect(csv).toContain(URBAN_CAVEAT);
    expect(csv).not.toContain('general one');
  });
});

describe('buildReport with targets', () => {
  const cells = normaliseCells(nested);
  const md = buildReport({
    summaries: summarizeTargets(cells, multiMeta, [0, 1]),
    meta: multiMeta,
    poly: ring,
    areaKm2: 1,
    url: 'https://example.test/',
    generatedAt: '2026-11-26T00:00:00Z',
  });

  it('has one results table per target', () => {
    expect(md).toContain('#### Natural habitat converted to crop');
    expect(md).toContain('#### Natural habitat converted to pasture and forage');
    expect(md).toContain('#### Natural habitat converted to urban and developed land');
    expect(md.match(/^\| Target \| Class \|/gm)).toHaveLength(3);
    expect(md).toContain('| Pasture | Forest |');
  });

  it('shows each lower-confidence caveat under its own table, not under crop', () => {
    const iCrop = md.indexOf('#### Natural habitat converted to crop');
    const iPasture = md.indexOf('#### Natural habitat converted to pasture');
    const iUrban = md.indexOf('#### Natural habitat converted to urban');
    expect(md.indexOf(`Lower confidence: ${PASTURE_CAVEAT}`)).toBeGreaterThan(iPasture);
    expect(md.indexOf(`Lower confidence: ${PASTURE_CAVEAT}`)).toBeLessThan(iUrban);
    expect(md.indexOf(`Lower confidence: ${URBAN_CAVEAT}`)).toBeGreaterThan(iUrban);
    expect(md.slice(iCrop, iPasture)).not.toContain('Lower confidence');
  });

  it('does not repeat the target caveats in the general list', () => {
    expect(md.split(PASTURE_CAVEAT)).toHaveLength(2);
    expect(md).toContain('- general one');
  });

  it('says targets are never added together', () => {
    expect(md).toContain('never added together');
    expect(md).not.toContain('\u2014');
  });

  it('a crop only report has no per-target sub-headings', () => {
    const one = buildReport({
      summaries: [summarize(normaliseCells(flat), baseMeta, [0, 1])],
      meta: baseMeta,
      poly: ring,
      areaKm2: 1,
      url: 'u',
      generatedAt: 't',
    });
    expect(one).not.toContain('#### ');
    expect(one).toContain('| Crop | Total |');
  });
});
