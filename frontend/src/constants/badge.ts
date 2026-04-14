/** 馬場状態に対応する daisyUI バッジクラス */
export const TRACK_CONDITION_CLASS: Record<string, string> = {
  良: 'badge-success',
  稍重: 'badge-warning',
  重: 'badge-error',
  不良: 'badge-error',
};

/** 着順に対応する daisyUI バッジクラス */
export const RANK_BADGE: Record<number, string> = {
  1: 'badge-warning',
  2: 'badge-ghost',
  3: 'badge-accent',
};

/** グレードに対応する daisyUI バッジクラス */
export const GRADE_CLASS: Record<string, string> = {
  G1: 'badge-error',
  G2: 'badge-warning',
  G3: 'badge-success',
};
