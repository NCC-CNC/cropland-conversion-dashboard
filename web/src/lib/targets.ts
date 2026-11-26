import type { Meta } from './types';

export const DEFAULT_TARGET = 'crop';

/** Short name used in sentences, for example "natural habitat converted to ...". */
export const TARGET_LABEL: Record<string, string> = {
  crop: 'crop',
  pasture: 'pasture and forage',
  urban: 'urban and developed land',
  barren: 'barren and exposed land',
};

/** Tab and row names. */
export const TARGET_SHORT: Record<string, string> = {
  crop: 'Cropland',
  pasture: 'Pasture',
  urban: 'Urban',
  barren: 'Barren',
};

/** Targets reported at lower confidence than crop. */
const LOWER_CONFIDENCE = ['pasture', 'urban', 'barren'];

export function targetLabel(t: string): string {
  return TARGET_LABEL[t] ?? t;
}

export function targetShort(t: string): string {
  return TARGET_SHORT[t] ?? t.charAt(0).toUpperCase() + t.slice(1);
}

/** Targets in the data. A file without `targets` is crop only. */
export function metaTargets(meta: Pick<Meta, 'targets'>): string[] {
  return meta.targets && meta.targets.length > 0 ? meta.targets : [DEFAULT_TARGET];
}

export function isLowerConfidence(target: string): boolean {
  return LOWER_CONFIDENCE.includes(target);
}

/**
 * Caveat text per lower-confidence target. The pipeline appends one caveat per
 * such target to the end of `meta.caveats`, in `targets` order (see the data
 * contract), so the last k entries belong to those k targets. The wording lives
 * in the pipeline only; it is not repeated here.
 */
export function targetCaveats(meta: Pick<Meta, 'targets' | 'caveats'>): Record<string, string> {
  const lower = metaTargets(meta).filter(isLowerConfidence);
  const out: Record<string, string> = {};
  if (lower.length === 0 || meta.caveats.length < lower.length) return out;
  const tail = meta.caveats.slice(meta.caveats.length - lower.length);
  lower.forEach((t, i) => (out[t] = tail[i]));
  return out;
}
