// レース情報
export interface Race {
  id: string;
  name: string;
  date: string; // ISO date string
  venue: string;
  course_type: '芝' | 'ダート';
  distance: number;
  weather: string | null;
  track_condition: '良' | '稍重' | '重' | '不良' | null;
  grade: 'G1' | 'G2' | 'G3';
}

// 馬情報
export interface Horse {
  id: string;
  name: string;
  sex: string | null;
  birthday: string | null;
  sire: string | null; // 父
  dam: string | null;  // 母
  dam_sire: string | null; // 母父
}

// 過去成績
export interface RaceResult {
  race_id: string;
  race_name: string;
  date: string;
  venue: string;
  distance: number;
  course_type: '芝' | 'ダート';
  track_condition: '良' | '稍重' | '重' | '不良';
  finish_position: number | null;
  time: string | null;
  last_3f: number | null;
}

// ファクター別スコア
export interface FactorScore {
  score: number;
  label: string;
  weighted: number;
}

// 予想結果
export interface Prediction {
  rank: number;
  horse_id: string;
  horse_name: string;
  total_score: number;
  factor_scores: Record<string, FactorScore>;
}

// データ取得進捗
export interface FetchProgress {
  status: 'idle' | 'running' | 'completed' | 'error';
  step: string;
  current: number;
  total: number;
  message: string;
  estimated_remaining: number | null; // 秒
}
