import { describe, expect, it } from 'vitest';
import { PIXEL_MAX_KM2, pixelColor, pixelFilter, pixelNote, pixelState, pmtilesPath } from './pixels';

const base = { available: true, enabled: true, areaKm2: 100, zoom: 12 };

describe('pixelState', () => {
  it('is visible for a small selection at tile zoom', () => {
    expect(pixelState(base)).toBe('visible');
  });
  it('treats the threshold as inclusive', () => {
    expect(pixelState({ ...base, areaKm2: PIXEL_MAX_KM2 })).toBe('visible');
    expect(pixelState({ ...base, areaKm2: PIXEL_MAX_KM2 + 0.1 })).toBe('too-large');
  });
  it('honours a custom threshold', () => {
    expect(pixelState({ ...base, areaKm2: 100, maxKm2: 50 })).toBe('too-large');
  });
  it('degrades without a file, before the toggle', () => {
    expect(pixelState({ ...base, available: false, enabled: false })).toBe('unavailable');
  });
  it('respects the toggle, selection and zoom', () => {
    expect(pixelState({ ...base, enabled: false })).toBe('off');
    expect(pixelState({ ...base, areaKm2: null })).toBe('no-selection');
    expect(pixelState({ ...base, zoom: 10.9 })).toBe('zoom-in');
    expect(pixelState({ ...base, zoom: 11 })).toBe('visible');
  });
});

describe('pixelNote', () => {
  it('has text only for guidance states', () => {
    expect(pixelNote('too-large')).toContain('500 km²');
    expect(pixelNote('zoom-in')).toContain('Zoom in');
    expect(pixelNote('visible')).toBe('');
    expect(pixelNote('unavailable')).toBe('');
  });
});

describe('pixelFilter', () => {
  it('matches interval and target', () => {
    expect(pixelFilter(2016, 'pasture')).toEqual([
      'all',
      ['==', ['get', 'interval'], 2016],
      ['==', ['get', 'target'], 'pasture'],
    ]);
  });
});

describe('misc', () => {
  it('colours known and unknown targets', () => {
    expect(pixelColor('urban')).not.toBe(pixelColor('crop'));
    expect(pixelColor('mystery')).toBe(pixelColor('crop'));
  });
  it('builds the file path', () => {
    expect(pmtilesPath('sk-mb')).toBe('sk-mb/converted.pmtiles');
  });
});
