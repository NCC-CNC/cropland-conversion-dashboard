import { describe, expect, it } from 'vitest';
import { buildCsv } from './csv';
import { visibleAreas } from './areas';
import { buildReport, coordinatesText, polygonVertices } from './report';
import {
  bboxIntersects,
  cellsInPolygon,
  makeRow,
  polygonBBox,
  selectionStatus,
  summarize,
} from './summary';
import type { Cells, Meta, PolygonGeometry } from './types';

// Four cells on a 2 x 2 lattice. Indices: 0=(0,0) 1=(1,0) 2=(0,1) 3=(1,1).
const cells: Cells = {
  lon: [0, 1, 0, 1],
  lat: [0, 0, 1, 1],
  area_ha: [100, 100, 100, 100],
  intervals: {
    '2011-2021': {
      natural_ha: { forest: [10, 20, 30, 40], grassland: [5, 5, 5, 5] },
      converted_ha: { forest: [1, 2, 3, 4], grassland: [0, 0, 1, 1] },
    },
  },
};

const meta: Meta = {
  area_id: 'tiny',
  name: 'Tiny',
  bbox: [-1, -1, 2, 2],
  cell_size_m: 1000,
  snapshots: [2011, 2021],
  latest: 2021,
  natural_classes: ['forest', 'grassland'],
  intervals: [{ from: 2011, to: 2021, years: 10 }],
  method: 'm',
  source: 'src, with comma',
  generated: '2026-01-01',
  caveats: [],
};

// Covers lon -0.5..1.5 and lat -0.5..0.5, so cells 0 and 1 only.
const poly: PolygonGeometry = {
  type: 'Polygon',
  coordinates: [
    [
      [-0.5, -0.5],
      [1.5, -0.5],
      [1.5, 0.5],
      [-0.5, 0.5],
      [-0.5, -0.5],
    ],
  ],
};

describe('cellsInPolygon', () => {
  it('selects cells whose centroid is inside', () => {
    expect(cellsInPolygon(cells, poly)).toEqual([0, 1]);
  });

  it('returns nothing for a polygon away from the data', () => {
    const far: PolygonGeometry = {
      type: 'Polygon',
      coordinates: [
        [
          [10, 10],
          [11, 10],
          [11, 11],
          [10, 11],
          [10, 10],
        ],
      ],
    };
    expect(cellsInPolygon(cells, far)).toEqual([]);
  });

  it('respects concave shapes, not just the bbox', () => {
    // L shape that excludes the (1,1) corner of the lattice.
    const l: PolygonGeometry = {
      type: 'Polygon',
      coordinates: [
        [
          [-0.5, -0.5],
          [1.5, -0.5],
          [1.5, 0.5],
          [0.5, 0.5],
          [0.5, 1.5],
          [-0.5, 1.5],
          [-0.5, -0.5],
        ],
      ],
    };
    expect(cellsInPolygon(cells, l)).toEqual([0, 1, 2]);
  });
});

describe('summarize (hand computed)', () => {
  const s = summarize(cells, meta, [0, 1]);

  it('sums hectares by class', () => {
    const iv = s.intervals[0];
    expect(iv.rows[0]).toMatchObject({ cls: 'forest', naturalHa: 30, convertedHa: 3 });
    expect(iv.rows[1]).toMatchObject({ cls: 'grassland', naturalHa: 10, convertedHa: 0 });
  });

  it('derives percent and annual rate', () => {
    const iv = s.intervals[0];
    expect(iv.rows[0].percent).toBeCloseTo(10, 10);
    expect(iv.rows[0].ratePerYear).toBeCloseTo(0.3, 10);
    expect(iv.total.naturalHa).toBe(40);
    expect(iv.total.convertedHa).toBe(3);
    expect(iv.total.percent).toBeCloseTo(7.5, 10);
    expect(iv.total.ratePerYear).toBeCloseTo(0.3, 10);
    expect(s.cellCount).toBe(2);
  });

  it('handles an empty selection', () => {
    const e = summarize(cells, meta, []);
    expect(e.intervals[0].total.naturalHa).toBe(0);
    expect(e.intervals[0].total.percent).toBeNull();
  });
});

describe('makeRow', () => {
  it('gives null percent when there is no natural cover', () => {
    expect(makeRow('forest', 0, 0, 5).percent).toBeNull();
  });
});

describe('selectionStatus', () => {
  const area: [number, number, number, number] = [0, 0, 10, 10];
  it('flags outside coverage', () => {
    expect(selectionStatus(0, [20, 20, 21, 21], area)).toBe('outside-coverage');
  });
  it('flags inside the area with no cells', () => {
    expect(selectionStatus(0, [1, 1, 2, 2], area)).toBe('no-natural-cells');
  });
  it('flags few cells below 5', () => {
    expect(selectionStatus(4, [1, 1, 2, 2], area)).toBe('few-cells');
    expect(selectionStatus(5, [1, 1, 2, 2], area)).toBe('ok');
  });
});

describe('bbox helpers', () => {
  it('computes polygon bbox and intersection', () => {
    expect(polygonBBox(poly)).toEqual([-0.5, -0.5, 1.5, 0.5]);
    expect(bboxIntersects([0, 0, 1, 1], [2, 2, 3, 3])).toBe(false);
    expect(bboxIntersects([0, 0, 2, 2], [1, 1, 3, 3])).toBe(true);
  });
});

describe('buildCsv', () => {
  const csv = buildCsv(summarize(cells, meta, [0, 1]), meta);
  const lines = csv.trim().split('\n');

  it('has a header and one row per class plus total', () => {
    expect(lines[0]).toContain('annual_rate_ha_per_year');
    expect(lines[1]).toBe('tiny,2011,2021,forest,30.00,3.00,10.00,0.30,2');
    expect(lines[3]).toBe('tiny,2011,2021,total,40.00,3.00,7.50,0.30,2');
  });

  it('quotes the note line containing commas', () => {
    expect(lines[lines.length - 1].startsWith('"')).toBe(true);
  });
});

describe('visibleAreas', () => {
  const fx = { id: 'demo-fixture', name: 'Demo (synthetic)', bbox: [0, 0, 1, 1] as [number, number, number, number] };
  const real = { id: 'sk', name: 'Saskatchewan', bbox: [0, 0, 1, 1] as [number, number, number, number] };
  it('keeps the fixture when it is the only area', () => {
    expect(visibleAreas([fx])).toEqual([fx]);
  });
  it('hides the fixture when real areas exist', () => {
    expect(visibleAreas([fx, real])).toEqual([real]);
  });
});

import { polygonAreaKm2 } from './geo';
import { decodeShare, encodeShare } from './share';

describe('polygonAreaKm2', () => {
  it('is close to 1 km2 for a 1 km square near the equator', () => {
    const d = 1 / 111.32;
    const poly = {
      type: 'Polygon' as const,
      coordinates: [[[0, 0], [d, 0], [d, d], [0, d], [0, 0]]],
    };
    expect(polygonAreaKm2(poly)).toBeGreaterThan(0.98);
    expect(polygonAreaKm2(poly)).toBeLessThan(1.02);
  });
});

describe('share links', () => {
  const poly = {
    type: 'Polygon' as const,
    coordinates: [[[-112.9, 52.2], [-112.6, 52.2], [-112.6, 52.4], [-112.9, 52.2]]],
  };
  it('round-trips area and shape', () => {
    const back = decodeShare(encodeShare('ab', poly));
    expect(back.area).toBe('ab');
    expect(back.poly?.coordinates[0]).toEqual(poly.coordinates[0]);
  });
  it('ignores malformed input', () => {
    expect(decodeShare('#a=x&s=nope')).toEqual({ area: 'x' });
    expect(decodeShare('')).toEqual({});
  });
});

describe('report', () => {
  const ring: PolygonGeometry = {
    type: 'Polygon',
    coordinates: [[[-112.123456789, 52.1], [-112, 52.1], [-112, 52.2], [-112.123456789, 52.1]]],
  };
  it('drops the closing point and rounds vertices', () => {
    const v = polygonVertices(ring);
    expect(v).toHaveLength(3);
    expect(v[0]).toEqual({ lon: -112.12346, lat: 52.1 });
  });
  it('lists coordinates as lat, lon', () => {
    expect(coordinatesText(ring).split('\n')[0]).toBe('1. 52.10000, -112.12346');
  });
  it('includes selection, statistics, methods and caveats', () => {
    const md = buildReport({
      summary: summarize(cells, meta, [0, 1]),
      meta,
      poly: ring,
      areaKm2: 12.34,
      url: 'https://example.test/#a=tiny',
      generatedAt: '2026-11-26T00:00:00Z',
    });
    for (const h of ['## Selection', '## Summary statistics', '## Methods', '## Caveats', '## Data source']) {
      expect(md).toContain(h);
    }
    expect(md).toContain('52.10000, -112.12346');
    expect(md).toContain('| Total |');
    expect(md).not.toContain('\u2014');
  });
});
