import { describe, expect, it } from 'vitest';
import { normaliseCells } from './data';
import { buildProvinceCard, provinceCodes } from './province';
import { summarize } from './summary';
import { cellsOfRegion, mergeCells, regionLabel, regionOptions, tilesForBBox, tilesForRegion, unionBBox } from './tiles';
import type { AreaIndex, Meta, ProvinceSummary, RawTile } from './types';

const index: AreaIndex = {
  area_id: 't',
  contract_version: 3,
  tile_m: 100000,
  cells: 5,
  regions: ['a-mb', 'b-sk'],
  region_summary: [
    { id: 'b-sk', name: 'Beta', cells: 3, area_ha: 300, tiles: ['0_0', '1_0'] },
    { id: 'a-mb', name: 'Alpha', cells: 2, area_ha: 200, tiles: ['1_0'] },
    { id: 'c-sk', name: 'Empty', cells: 0, area_ha: 0, tiles: [] },
  ],
  tiles: [
    { id: '0_0', file: 'tiles/0_0.json', bbox: [-110, 50, -109, 51], cells: 2, bytes: 1, regions: { 'b-sk': 2 } },
    { id: '1_0', file: 'tiles/1_0.json', bbox: [-108, 50, -107, 51], cells: 3, bytes: 1, regions: { 'a-mb': 2, 'b-sk': 1 } },
  ],
};

// Tile 0_0 omits the pasture target and the grassland class; tile 1_0 has both.
const t0: RawTile = {
  lon: [-109.5, -109.4], lat: [50.5, 50.6], area_ha: [100, 100], region: [1, 1],
  intervals: { '2011-2021': { natural_ha: { forest: [10, 20] }, converted_ha: { crop: { forest: [1, 2] } } } },
};
const t1: RawTile = {
  lon: [-107.5, -107.4, -107.3], lat: [50.5, 50.6, 50.7], area_ha: [100, 100, 100], region: [0, 0, 1],
  intervals: {
    '2011-2021': {
      natural_ha: { forest: [5, 5, 5], grassland: [7, 7, 7] },
      converted_ha: { crop: { forest: [1, 0, 0], grassland: [0, 1, 1] }, pasture: { grassland: [2, 0, 0] } },
    },
  },
};

const meta = {
  natural_classes: ['forest', 'grassland'],
  targets: ['crop', 'pasture'],
  intervals: [{ from: 2011, to: 2021, years: 10 }],
} as unknown as Meta;

describe('tile selection', () => {
  it('picks tiles whose bbox intersects', () => {
    expect(tilesForBBox(index, [-109.9, 50.2, -109.2, 50.4]).map((t) => t.id)).toEqual(['0_0']);
    expect(tilesForBBox(index, [-110, 50, -107, 51]).map((t) => t.id)).toEqual(['0_0', '1_0']);
    expect(tilesForBBox(index, [-100, 50, -99, 51])).toEqual([]);
  });
  it('picks region tiles in index order and ignores unknown regions', () => {
    expect(tilesForRegion(index, 'b-sk').map((t) => t.id)).toEqual(['0_0', '1_0']);
    expect(tilesForRegion(index, 'a-mb').map((t) => t.id)).toEqual(['1_0']);
    expect(tilesForRegion(index, 'nope')).toEqual([]);
  });
  it('unions boxes', () => {
    expect(unionBBox(index.tiles)).toEqual([-110, 50, -107, 51]);
    expect(unionBBox([])).toBeNull();
  });
  it('lists regions with cells, by name, labelled with province', () => {
    expect(regionOptions(index).map((r) => r.id)).toEqual(['a-mb', 'b-sk']);
    expect(regionLabel({ id: 'a-mb', name: 'Alpha' })).toBe('Alpha (MB)');
  });
});

describe('merging tiles', () => {
  const merged = mergeCells([normaliseCells(t0), normaliseCells(t1)]);

  it('concatenates and zero-fills classes and targets a tile left out', () => {
    expect(merged.lon).toHaveLength(5);
    expect(merged.region).toEqual([1, 1, 0, 0, 1]);
    const iv = merged.intervals['2011-2021'];
    expect(iv.natural_ha.grassland).toEqual([0, 0, 7, 7, 7]);
    expect(iv.converted_ha.pasture.forest).toEqual([0, 0, 0, 0, 0]);
    expect(iv.converted_ha.pasture.grassland).toEqual([0, 0, 2, 0, 0]);
  });

  it('sums the same as summing each tile', () => {
    const all = summarize(merged, meta, [0, 1, 2, 3, 4], 'crop').intervals[0].total;
    const a = summarize(normaliseCells(t0), meta, [0, 1], 'crop').intervals[0].total;
    const b = summarize(normaliseCells(t1), meta, [0, 1, 2], 'crop').intervals[0].total;
    expect(all.naturalHa).toBe(a.naturalHa + b.naturalHa);
    expect(all.convertedHa).toBe(a.convertedHa + b.convertedHa);
  });

  it('keeps one region by index', () => {
    const r = cellsOfRegion(merged, index, 'a-mb');
    expect(r.lon).toEqual([-107.5, -107.4]);
    expect(r.intervals['2011-2021'].converted_ha.crop.grassland).toEqual([0, 1]);
    expect(cellsOfRegion(merged, index, 'nope').lon).toEqual([]);
  });

  it('handles a tile without a region column', () => {
    const noRegion: RawTile = { ...t1, region: undefined };
    const m = mergeCells([normaliseCells(t0), normaliseCells(noRegion)]);
    expect(m.region).toEqual([1, 1, -1, -1, -1]);
  });
});

const cov = (complete: boolean) => ({
  complete,
  regions_total: 14,
  regions_run: ['a-mb', 'b-sk'],
  regions_covered: complete ? ['a-mb', 'b-sk'] : [],
  farming_zone_area_km2: 600000,
  covered_area_km2: 21000,
  fraction: 0.035,
});

function summaryWith(complete: boolean): ProvinceSummary {
  const iv = {
    natural_ha: { forest: 100 },
    converted_ha: { crop: { forest: 5 } },
    converted_pct: { crop: { forest: 5 } },
    total: { natural_ha: 100, converted_ha: { crop: 5 }, converted_pct: { crop: 5 } },
  };
  return {
    kind: 'province_summary', area_id: 't', generated: '2026-11-26', latest: 2021,
    years: { snapshots: [2011, 2021], intervals: [{ from: 2011, to: 2021, years: 10 }] },
    natural_classes: ['forest'], targets: ['crop', 'pasture'], method: '', source: '', caveats: [],
    coverage: cov(complete),
    provinces: {
      all: { name: 'Manitoba and Saskatchewan', regions: ['a-mb', 'b-sk'], cells: 5, area_ha: 500, coverage: cov(complete), intervals: { '2011-2021': iv } },
      MB: { name: 'Manitoba', regions: ['a-mb'], cells: 2, area_ha: 200, coverage: cov(complete), intervals: { '2011-2021': iv } },
    },
  };
}

describe('province card', () => {
  it('never says total or provincial when coverage is incomplete', () => {
    const m = buildProvinceCard(summaryWith(false), 'MB', (id) => id)!;
    expect(m.provincial).toBe(false);
    expect(m.heading).not.toMatch(/total/i);
    expect(m.coverageText).toMatch(/not a Manitoba total/);
    expect(m.coverageText).toContain('2 of 14');
    expect(m.regionsRun).toEqual(['a-mb']);
  });
  it('says total only when complete is true', () => {
    const m = buildProvinceCard(summaryWith(true), 'MB')!;
    expect(m.provincial).toBe(true);
    expect(m.heading).toBe('Manitoba total');
  });
  it('treats a missing complete flag as incomplete', () => {
    const s = summaryWith(true);
    delete (s.provinces.MB.coverage as { complete?: boolean }).complete;
    expect(buildProvinceCard(s, 'MB')!.provincial).toBe(false);
  });
  it('reads rows per target and interval, null for a missing percent', () => {
    const m = buildProvinceCard(summaryWith(false), 'all')!;
    expect(m.name).toBe('Manitoba and Saskatchewan');
    expect(m.intervals[0].rows).toEqual([
      { target: 'crop', convertedHa: 5, percent: 5 },
      { target: 'pasture', convertedHa: 0, percent: null },
    ]);
  });
  it('lists codes present and returns null for others', () => {
    expect(provinceCodes(summaryWith(false))).toEqual(['MB', 'all']);
    expect(buildProvinceCard(summaryWith(false), 'SK')).toBeNull();
  });
});
