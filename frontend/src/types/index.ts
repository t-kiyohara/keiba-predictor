/* backend/app/schemas と data-contract.md v2 に対応する型。
   バックエンドの Pydantic はいずれも `str | None` なので、閉じたリテラル union は張らない
   (実データに 'OP' やスクレイプ由来の想定外文字列が現れる)。表示側は必ずフォールバックを持つ。 */

/** 確定着順の1頭(データ契約 v2)。races.json は上位3頭、races/{id}.json は全着順 */
export interface RaceFinisher {
  horse_id: string;
  horse_name: string;
  horse_number: number | null;
  finish_position: number;
  /** 騎手・タイム・着差・上がり3F。結果ページ由来。未取得なら null */
  jockey_name?: string | null;
  time?: string | null;
  margin?: string | null;
  last_3f?: number | null;
}

/** 払戻(100円あたり)。place のキーは馬番の文字列 */
export interface RacePayouts {
  win: number | null;
  place: Record<string, number>;
}

/** レース情報。top_pick / results / payouts は静的データ契約のみが持つ(API モードでは undefined) */
export interface Race {
  id: string;
  name: string;
  date: string; // ISO date (YYYY-MM-DD)
  venue: string;
  course_type: string; // 芝 / ダート / 障
  distance: number;
  weather: string | null;
  track_condition: string | null; // 良 / 稍重 / 重 / 不良。未取得なら null
  grade: string; // G1 / G2 / G3 / OP など
  /** 最新予想の rank=1。予想未生成なら null、未取得なら undefined */
  top_pick?: TopPick | null;
  /** 確定着順。未収集なら空配列、未取得なら undefined */
  results?: RaceFinisher[];
  /** 払戻。未収集なら null、未取得なら undefined */
  payouts?: RacePayouts | null;
}

export interface TopPick {
  horse_id: string;
  horse_name: string;
  total_score: number;
  /** ◎の確定着順。未収集なら null、未取得なら undefined */
  finish_position?: number | null;
}

/** 出走馬(馬柱の枠色・馬番・オッズ・騎手の出所) */
export interface Entry {
  horse_id: string;
  horse_number: number | null;
  post_position: number | null; // 枠番
  weight: number | null; // 斤量
  odds: number | null;
  jockey_name: string | null;
  sex: string | null;
  age: number | null;
  /** 対象レースより前の着順(新しい順・最大5件)。未取得なら undefined */
  recent_finishes?: number[];
}

/** 馬情報 */
export interface Horse {
  id: string;
  name: string;
  sex: string | null;
  birthday: string | null;
  sire: string | null; // 父
  dam: string | null; // 母
  dam_sire: string | null; // 母父
}

/** 過去成績 */
export interface RaceResult {
  race_id: string;
  race_name: string;
  date: string;
  venue: string;
  distance: number;
  course_type: string;
  track_condition: string | null;
  finish_position: number | null;
  time: string | null;
  last_3f: number | null;
  /** 静的データ契約のみ。API モードでは undefined */
  grade?: string | null;
  margin?: string | null;
  jockey_name?: string | null;
}

/** ファクター別スコア */
export interface FactorScore {
  score: number;
  label: string;
  weighted: number;
}

/** 予想結果 */
export interface Prediction {
  rank: number;
  horse_id: string;
  horse_name: string;
  total_score: number;
  factor_scores: Record<string, FactorScore>;
}

/** データ取得進捗 */
export interface FetchProgress {
  status: 'idle' | 'running' | 'completed' | 'error';
  step: string;
  current: number;
  total: number;
  message: string;
  estimated_remaining: number | null; // 秒
}

/** データ生成時刻(静的ビルドの meta.json) */
export interface DataMeta {
  generated_at: string;
  race_count?: number;
}

/** 的中実績(data-contract.md の stats.json) */
export interface StatsSummary {
  races: number;
  win_hit_rate: number;
  win_roi: number;
  place_hit_rate: number;
  place_roi: number;
  top3_in_top_picks: number;
}

export interface StatsCumulativePoint {
  date: string;
  race_id: string;
  balance_win: number;
  balance_place: number;
}

export interface StatsRow {
  date: string;
  race_id: string;
  race_name: string;
  grade: string;
  venue: string;
  pick_horse_name: string;
  pick_odds: number | null;
  finish_position: number | null;
  win_payout: number;
  place_payout: number;
  net: number;
}

export interface Stats {
  summary: StatsSummary;
  cumulative: StatsCumulativePoint[];
  rows: StatsRow[];
}
