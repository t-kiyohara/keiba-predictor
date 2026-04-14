/** 馬場状態バッジの SmartHR スタイル（badge-smarthr + 色ユーティリティ） */
export const TRACK_CONDITION_CLASS: Record<string, string> = {
  良: 'badge-smarthr bg-emerald-100 text-emerald-700',
  稍重: 'badge-smarthr bg-yellow-100 text-yellow-700',
  重: 'badge-smarthr bg-orange-100 text-orange-700',
  不良: 'badge-smarthr bg-red-100 text-red-700',
};

/** 着順バッジの SmartHR スタイル */
export const RANK_BADGE: Record<number, string> = {
  1: 'badge-smarthr bg-yellow-400/30 text-yellow-700',
  2: 'badge-smarthr bg-slate-200 text-slate-600',
  3: 'badge-smarthr bg-amber-200 text-amber-700',
};

/** グレードバッジの SmartHR スタイル */
export const GRADE_CLASS: Record<string, string> = {
  G1: 'badge-smarthr bg-danger/10 text-danger border border-danger/30',
  G2: 'badge-smarthr bg-warning/20 text-stone-04 border border-warning/30',
  G3: 'badge-smarthr bg-primary/10 text-primary border border-primary/30',
};
