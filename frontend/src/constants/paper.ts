/* 紙面の語彙(DESIGN.md §2「グレード章」「枠色」/ §1「印の言語」)。
   バックエンドの値は自由文字列なので、どのマップも必ずフォールバックを持つ。 */

/* クラス名は文字列リテラルで持つ。テンプレートリテラルで組み立てると
   Tailwind の content スキャンから漏れ、@layer components ごと削除される。 */

const GRADE_BADGE_CLASS: Record<string, string> = {
  G1: 'badge-grade badge-grade-g1',
  G2: 'badge-grade badge-grade-g2',
  G3: 'badge-grade badge-grade-g3',
};
const GRADE_BADGE_CLASS_OTHER = 'badge-grade badge-grade-op';

/** グレード章のクラス。G1/G2/G3 以外(OP・L・重賞外)は白地×墨×罫線囲み */
export function gradeBadgeClass(grade: string): string {
  return GRADE_BADGE_CLASS[grade] ?? GRADE_BADGE_CLASS_OTHER;
}

const WAKU_CHIP_CLASS = [
  'chip-waku chip-waku-1',
  'chip-waku chip-waku-2',
  'chip-waku chip-waku-3',
  'chip-waku chip-waku-4',
  'chip-waku chip-waku-5',
  'chip-waku chip-waku-6',
  'chip-waku chip-waku-7',
  'chip-waku chip-waku-8',
];

/** 枠色チップのクラス。枠番不明時は罫線囲みの中立チップ(1枠=白と同じ見た目) */
export function wakuChipClass(postPosition: number | null | undefined): string {
  if (postPosition === null || postPosition === undefined) return WAKU_CHIP_CLASS[0];
  const waku = Math.min(8, Math.max(1, postPosition));
  return WAKU_CHIP_CLASS[waku - 1];
}

export interface Mark {
  symbol: string;
  /** 読み上げ用の呼称(DESIGN.md §7) */
  label: string;
}

/** 予想順位 → 印。◎(1位)○(2位)▲(3位)△(4–5位)。6位以下は印なし */
const MARK_BY_RANK: Record<number, Mark> = {
  1: { symbol: '◎', label: '本命' },
  2: { symbol: '○', label: '対抗' },
  3: { symbol: '▲', label: '単穴' },
  4: { symbol: '△', label: '連下' },
  5: { symbol: '△', label: '連下' },
};

export function markForRank(rank: number): Mark | null {
  return MARK_BY_RANK[rank] ?? null;
}

/** ◎ のみ朱、他は墨(DESIGN.md §1「1画面に朱の面積は1割未満」) */
export function markColorClass(rank: number): string {
  return rank === 1 ? 'text-shu' : 'text-ink';
}

/** 印の凡例(ファクター欄の下に小さく置く) */
export const MARK_LEGEND: { symbol: string; label: string; note: string }[] = [
  { symbol: '◎', label: '本命', note: '予想1位' },
  { symbol: '○', label: '対抗', note: '2位' },
  { symbol: '▲', label: '単穴', note: '3位' },
  { symbol: '△', label: '連下', note: '4・5位' },
];

/* 天気の記号。末尾の U+FE0E(VS15)で絵文字表示を抑え、墨の単色グリフにする */
const WEATHER_GLYPH: Record<string, string> = {
  晴: '☀︎',
  晴れ: '☀︎',
  曇: '☁︎',
  曇り: '☁︎',
  雨: '☂︎',
  小雨: '☂︎',
  雪: '❅',
};

export function weatherGlyph(weather: string | null): string | null {
  if (!weather) return null;
  return WEATHER_GLYPH[weather] ?? '☁︎';
}

/** CSS 変数を解釈しない箇所(Chart.js)向けに :root の実際の色を取り出す */
export function paperColor(
  name: 'ink' | 'ink-weak' | 'rule' | 'shu' | 'ai' | 'paper',
): string {
  const resolved = getComputedStyle(document.documentElement)
    .getPropertyValue(`--${name}`)
    .trim();
  return resolved || '#1C1A17';
}

const WEEKDAY = ['日', '月', '火', '水', '木', '金', '土'];

/** '2026-08-30' → '8月30日(日)'。日付見出し用 */
export function formatPaperDate(isoDate: string): string {
  const [year, month, day] = isoDate.split('-').map(Number);
  if (!year || !month || !day) return isoDate;
  const weekday = WEEKDAY[new Date(year, month - 1, day).getDay()];
  return `${month}月${day}日(${weekday})`;
}

/** '2026-08-30' → '2026年8月30日(日)'。レース詳細の見出し用 */
export function formatPaperDateFull(isoDate: string): string {
  const [year] = isoDate.split('-').map(Number);
  if (!year) return isoDate;
  return `${year}年${formatPaperDate(isoDate)}`;
}

/** ISO日時 → '2026/09/05 06:02'。更新日時表示用 */
export function formatTimestamp(isoDateTime: string): string {
  const parsed = new Date(isoDateTime);
  if (Number.isNaN(parsed.getTime())) return isoDateTime;
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${parsed.getFullYear()}/${pad(parsed.getMonth() + 1)}/${pad(parsed.getDate())} ${pad(parsed.getHours())}:${pad(parsed.getMinutes())}`;
}

/** レース番号は race_id の末尾2桁(netkeiba 仕様: YYYY+場+回+日+R) */
export function raceNumberFromId(raceId: string): string | null {
  const match = raceId.match(/(\d{2})$/);
  if (!match) return null;
  const raceNumber = Number(match[1]);
  return raceNumber >= 1 && raceNumber <= 12 ? `${raceNumber}R` : null;
}

/* 天気の表記ゆれを紙面の1文字に寄せる(「晴れ」→「晴」/「曇り」→「曇」) */
export function formatWeather(weather: string | null): string | null {
  if (!weather) return null;
  return weather.replace(/(晴)れ$/, '$1').replace(/(曇)り$/, '$1');
}

/* 括弧内のグレード表記。グレード章(badge)で既に出ているのでレース名からは落とす。
   NFKC 正規化後は全角括弧・ローマ数字も ASCII になっている(Ⅲ→III) */
const GRADE_IN_NAME_PATTERN = /[(](?:J[・.]?\s*)?G\s*(?:III|II|I|1|2|3)[)]/g;

/* 専門紙の略記 → 正式表記。長い略記から先に判定する */
const NAME_ABBREVIATIONS: [string, string][] = [
  ['AH', 'オータムハンデキャップ'],
  ['JS', 'ジャンプステークス'],
  ['CT', 'チャレンジトロフィー'],
  ['S', 'ステークス'],
  ['C', 'カップ'],
  ['T', 'トロフィー'],
  ['H', 'ハンデキャップ'],
  ['D', 'ダッシュ'],
];

/** 末尾の略記を正式表記に展開(「紫苑S」→「紫苑ステークス」)。
    直前が英大文字の場合は略号そのもの(AJCC 等)とみなして触らない */
function expandAbbreviation(name: string): string {
  for (const [abbreviation, expanded] of NAME_ABBREVIATIONS) {
    if (!name.endsWith(abbreviation)) continue;
    const stem = name.slice(0, -abbreviation.length);
    if (stem.length === 0 || /[A-Z]$/.test(stem)) return name;
    return `${stem}${expanded}`;
  }
  return name;
}

/** '第62回新潟記念(GIII)' → { title: '新潟記念', edition: '第62回' }。
    回次はキャプションに分け、レース名本体だけを明朝の見出しに載せる */
export function splitRaceName(name: string): { title: string; edition: string | null } {
  const normalized = name.normalize('NFKC').replace(GRADE_IN_NAME_PATTERN, '').trim();
  const editionMatch = normalized.match(/^第\s*(\d+)\s*回\s*/);
  const body = editionMatch ? normalized.slice(editionMatch[0].length) : normalized;
  return {
    title: expandAbbreviation(body.trim()) || normalized,
    edition: editionMatch ? `第${editionMatch[1]}回` : null,
  };
}

/** 馬番 → 枠番(JRA の枠順割り)。8頭以下は枠=馬番、9頭以上は8枠に後ろから詰める。
    確定結果には枠番が無いので、結果表の枠色チップはこれで色付けする */
export function wakuFromHorseNumber(
  horseNumber: number | null,
  headCount: number,
): number | null {
  if (horseNumber === null || horseNumber < 1) return null;
  if (headCount <= 8) return horseNumber <= 8 ? horseNumber : 8;

  const horsesPerWaku = Math.floor(headCount / 8);
  const wakuWithExtraHorse = headCount % 8;
  let lastHorseNumberInWaku = 0;
  for (let waku = 1; waku <= 8; waku += 1) {
    lastHorseNumberInWaku +=
      waku > 8 - wakuWithExtraHorse ? horsesPerWaku + 1 : horsesPerWaku;
    if (horseNumber <= lastHorseNumberInWaku) return waku;
  }
  return 8;
}

/** 着順1–3着は墨太字、1着のみ朱(DESIGN.md §5-4)。戦績表・結果欄・馬柱で共用 */
export function finishClass(finishPosition: number | null): string {
  if (finishPosition === 1) return 'font-bold text-shu';
  if (finishPosition !== null && finishPosition <= 3) return 'font-bold text-ink';
  return 'text-ink-weak';
}
