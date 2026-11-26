import type { Interval, Meta } from './types';

/** Interval label such as "2011 to 2025". */
export function intervalName(iv: Pick<Interval, 'from' | 'to'>): string {
  return `${iv.from} to ${iv.to}`;
}

/** Tab label. An interval with a note says so in words, so the cue is not colour only. */
export function intervalTabLabel(iv: Pick<Interval, 'from' | 'to' | 'note'>): string {
  return iv.note ? `${intervalName(iv)} (caution)` : intervalName(iv);
}

/** Note for the interval with these years, or undefined. Older files have none. */
export function intervalNote(meta: Pick<Meta, 'intervals'>, from: number, to: number): string | undefined {
  const n = meta.intervals.find((iv) => iv.from === from && iv.to === to)?.note;
  return n && n.trim() ? n : undefined;
}
