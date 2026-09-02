import type { CSSProperties } from 'react';
import { Entry, Prediction } from '../types';
import {
  finishClass,
  markColorClass,
  markForRank,
  wakuChipClass,
} from '../constants/paper';

interface Props {
  predictions: Prediction[];
  entries: Entry[];
  selectedHorseId: string | null;
  onSelect: (horseId: string) => void;
  /** 確定着順(horse_id → 着)。未収集なら渡さない */
  finishByHorseId?: Record<string, number>;
}

interface HorseColumn {
  horseId: string;
  horseName: string;
  rank: number;
  totalScore: number;
  horseNumber: number | null;
  postPosition: number | null;
  odds: number | null;
  jockeyName: string | null;
  build: string | null; // 性齢・斤量
  recentFinishes: number[]; // 近走の着順(新しい順)
  finishPosition: number | null; // このレースの確定着順
}

/** 行の高さ。ラベル列と馬列で共有し、横方向の行合わせを崩さない */
const CELL = {
  chip: 'h-7',
  mark: 'h-8',
  name: 'h-40',
  build: 'h-6',
  jockey: 'h-[4.5rem]',
  recent: 'h-[5.5rem]',
  odds: 'h-6',
  score: 'h-[4.5rem]',
  finish: 'h-7',
} as const;

type CellRow = keyof typeof CELL;

const ROW_LABELS: [CellRow, string][] = [
  ['chip', '枠・馬番'],
  ['mark', '印'],
  ['name', '馬名'],
  ['build', '性齢・斤量'],
  ['jockey', '騎手'],
  ['recent', '近走'],
  ['odds', '単勝'],
  ['score', 'スコア'],
  ['finish', '着順'],
];

/** 上に細罫を引く行。予想の欄(スコア)と結果の欄(着順)を仕切る */
const ROWS_WITH_TOP_RULE: CellRow[] = ['score', 'finish'];

function buildColumns(
  predictions: Prediction[],
  entries: Entry[],
  finishByHorseId: Record<string, number>,
): HorseColumn[] {
  const entryByHorseId = new Map(entries.map((entry) => [entry.horse_id, entry]));

  const columns = predictions.map((prediction): HorseColumn => {
    const entry = entryByHorseId.get(prediction.horse_id);
    const sexAge = entry
      ? [entry.sex, entry.age !== null ? `${entry.age}` : null].filter(Boolean).join('')
      : '';
    const weight = entry?.weight !== null && entry?.weight !== undefined ? `${entry.weight}` : '';
    return {
      horseId: prediction.horse_id,
      horseName: prediction.horse_name,
      rank: prediction.rank,
      totalScore: prediction.total_score,
      horseNumber: entry?.horse_number ?? null,
      postPosition: entry?.post_position ?? null,
      odds: entry?.odds ?? null,
      jockeyName: entry?.jockey_name ?? null,
      build: [sexAge, weight].filter(Boolean).join(' ') || null,
      recentFinishes: entry?.recent_finishes ?? [],
      finishPosition: finishByHorseId[prediction.horse_id] ?? null,
    };
  });

  // 馬番が全頭そろっているときだけ紙の出馬表と同じ並び(馬番昇順・右→左)にする。
  // 出走馬データが無い場合(API に entries が無い等)は予想順で左→右に並べる。
  const hasHorseNumbers = columns.every((column) => column.horseNumber !== null);
  columns.sort((left, right) =>
    hasHorseNumbers
      ? (left.horseNumber ?? 0) - (right.horseNumber ?? 0)
      : left.rank - right.rank,
  );
  return columns;
}

function wakuLabel(column: HorseColumn): string {
  const waku = column.postPosition !== null ? `${column.postPosition}枠` : '';
  const umaban = column.horseNumber !== null ? `${column.horseNumber}番` : '';
  return `${waku}${umaban}` || column.horseName;
}

function ScoreBar({
  totalScore,
  rank,
  orientation,
}: {
  totalScore: number;
  rank: number;
  orientation: 'vertical' | 'horizontal';
}) {
  // スコアは 0–100 の絶対値なので 100 を満尺とする(レース間で高さが比較できる)
  const ratio = Math.min(1, Math.max(0.02, totalScore / 100));
  const inkClass = rank === 1 ? 'bg-shu' : 'bg-ink';

  if (orientation === 'vertical') {
    return (
      <div className="flex h-12 w-1.5 flex-col justify-end bg-rule" aria-hidden="true">
        <div className={inkClass} style={{ height: `${ratio * 100}%` }} />
      </div>
    );
  }
  return (
    <div className="h-1.5 w-16 bg-rule" aria-hidden="true">
      <div className={`h-full ${inkClass}`} style={{ width: `${ratio * 100}%` }} />
    </div>
  );
}

function MarkGlyph({ rank, stampIndex }: { rank: number; stampIndex: number }) {
  const mark = markForRank(rank);
  if (!mark) return <span aria-hidden="true">&nbsp;</span>;
  return (
    <span
      className={`mark stamp ${markColorClass(rank)}`}
      style={{ '--stamp-index': stampIndex } as CSSProperties}
      aria-label={mark.label}
      role="img"
    >
      {mark.symbol}
    </span>
  );
}

export default function Umabashira({
  predictions,
  entries,
  selectedHorseId,
  onSelect,
  finishByHorseId = {},
}: Props) {
  const columns = buildColumns(predictions, entries, finishByHorseId);

  // 全頭で欠けている項目は行ごと落とす(「–」だけの行を紙面に残さない)
  const rowVisible: Record<CellRow, boolean> = {
    chip: columns.some(
      (column) => column.horseNumber !== null || column.postPosition !== null,
    ),
    mark: true,
    name: true,
    build: columns.some((column) => column.build !== null),
    jockey: columns.some((column) => column.jockeyName !== null),
    recent: columns.some((column) => column.recentFinishes.length > 0),
    odds: columns.some((column) => column.odds !== null),
    score: true,
    finish: columns.some((column) => column.finishPosition !== null),
  };

  return (
    <>
      {/* 縦組みの馬柱(768px 以上)。馬番の右→左に並べる。
          dir="rtl" にすることで、はみ出した列が左方向にスクロールできる
          (flex-row-reverse だと左側のオーバーフローがスクロール不能になる)。 */}
      <div className="flex sp:hidden">
        <div className="shrink-0 pr-2 text-right">
          {ROW_LABELS.filter(([row]) => rowVisible[row]).map(([row, label]) => (
            <div
              key={row}
              className={`${CELL[row]} flex items-center justify-end text-caption
                text-ink-weak ${ROWS_WITH_TOP_RULE.includes(row) ? 'rule-t' : ''}`}
            >
              {label}
            </div>
          ))}
        </div>

        {/* max-w-fit: 頭数が少ないときは列をラベル列の隣に寄せ、
            はみ出すときだけ横スクロールにする */}
        <div className="min-w-0 max-w-fit flex-1 overflow-x-auto" dir="rtl">
          <ul className="flex">
            {columns.map((column, index) => {
              const isSelected = column.horseId === selectedHorseId;
              return (
                <li key={column.horseId} className="shrink-0 border-l border-rule">
                  <button
                    type="button"
                    dir="ltr"
                    onClick={() => onSelect(column.horseId)}
                    aria-pressed={isSelected}
                    className={`flex w-[68px] flex-col items-center transition-colors
                      hover:bg-paper-inset ${isSelected ? 'bg-paper-inset' : ''}`}
                  >
                    {rowVisible.chip && (
                      <span className={`${CELL.chip} flex items-center justify-center`}>
                        <span
                          className={wakuChipClass(column.postPosition)}
                          aria-label={wakuLabel(column)}
                        >
                          {column.horseNumber ?? '–'}
                        </span>
                      </span>
                    )}

                    <span className={`${CELL.mark} flex items-center justify-center`}>
                      <MarkGlyph rank={column.rank} stampIndex={index} />
                    </span>

                    <span
                      className={`${CELL.name} overflow-hidden pt-1 font-mincho
                        text-[15px] font-bold leading-tight text-ink tategaki`}
                    >
                      {column.horseName}
                    </span>

                    {rowVisible.build && (
                      <span
                        className={`${CELL.build} flex items-center justify-center
                          text-caption tabular-nums text-ink-weak`}
                      >
                        {column.build ?? '–'}
                      </span>
                    )}

                    {rowVisible.jockey && (
                      <span
                        className={`${CELL.jockey} overflow-hidden text-[11px]
                          leading-tight text-ink-weak tategaki`}
                      >
                        {column.jockeyName ?? '–'}
                      </span>
                    )}

                    {rowVisible.recent && (
                      <span
                        className={`${CELL.recent} flex flex-col items-center
                          justify-center gap-0.5 text-[11px] leading-none
                          tabular-nums`}
                      >
                        {column.recentFinishes.length > 0
                          ? column.recentFinishes.map((finishPosition, order) => (
                              <span
                                key={`${finishPosition}-${order}`}
                                className={finishClass(finishPosition)}
                              >
                                {finishPosition}
                              </span>
                            ))
                          : <span className="text-ink-weak">–</span>}
                      </span>
                    )}

                    {rowVisible.odds && (
                      <span
                        className={`${CELL.odds} flex items-center justify-center
                          text-caption tabular-nums text-ink`}
                      >
                        {column.odds !== null ? column.odds.toFixed(1) : '–'}
                      </span>
                    )}

                    <span
                      className={`${CELL.score} rule-t flex w-full flex-col items-center
                        justify-end gap-1 pb-1`}
                    >
                      <span
                        className={`text-data font-bold tabular-nums ${
                          column.rank === 1 ? 'text-shu' : 'text-ink'
                        }`}
                      >
                        {column.totalScore.toFixed(1)}
                      </span>
                      <ScoreBar
                        totalScore={column.totalScore}
                        rank={column.rank}
                        orientation="vertical"
                      />
                    </span>

                    {rowVisible.finish && (
                      <span
                        className={`${CELL.finish} rule-t flex w-full items-center
                          justify-center text-data tabular-nums
                          ${finishClass(column.finishPosition)}`}
                      >
                        {column.finishPosition !== null ? `${column.finishPosition}着` : '–'}
                      </span>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      </div>

      {/* 768px 未満は縦組みを捨て、1頭=1行の横テーブルにフォールバック(DESIGN.md §4) */}
      <div className="hidden overflow-x-auto sp:block">
        <table className="w-full border-collapse text-data">
          <caption className="sr-only">出走馬と総合スコア</caption>
          <thead>
            <tr className="bg-paper-inset text-left text-caption text-ink-weak">
              {rowVisible.chip && (
                <th scope="col" className="px-2 py-1 font-medium">
                  枠馬番
                </th>
              )}
              <th scope="col" className="px-1 py-1 font-medium">
                印
              </th>
              <th scope="col" className="px-2 py-1 font-medium">
                馬名
              </th>
              {rowVisible.jockey && (
                <th scope="col" className="px-2 py-1 font-medium">
                  騎手
                </th>
              )}
              {rowVisible.recent && (
                <th scope="col" className="px-2 py-1 font-medium">
                  近走
                </th>
              )}
              {rowVisible.odds && (
                <th scope="col" className="px-2 py-1 text-right font-medium">
                  単勝
                </th>
              )}
              <th scope="col" className="px-2 py-1 text-right font-medium">
                スコア
              </th>
              {rowVisible.finish && (
                <th scope="col" className="px-2 py-1 text-right font-medium">
                  着順
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {columns.map((column, index) => {
              const isSelected = column.horseId === selectedHorseId;
              return (
                <tr
                  key={column.horseId}
                  onClick={() => onSelect(column.horseId)}
                  className={`cursor-pointer border-t border-rule transition-colors
                    hover:bg-paper-inset ${isSelected ? 'bg-paper-inset' : ''}`}
                >
                  {rowVisible.chip && (
                    <td className="px-2 py-1.5">
                      <span
                        className={wakuChipClass(column.postPosition)}
                        aria-label={wakuLabel(column)}
                      >
                        {column.horseNumber ?? '–'}
                      </span>
                    </td>
                  )}
                  <td className="px-1 py-1.5 text-center">
                    <MarkGlyph rank={column.rank} stampIndex={index} />
                  </td>
                  <td className="px-2 py-1.5">
                    {/* 行全体もタップできるが、キーボード操作の到達点をここに置く */}
                    <button
                      type="button"
                      onClick={() => onSelect(column.horseId)}
                      aria-pressed={isSelected}
                      className="text-left font-mincho font-bold text-ink"
                    >
                      {column.horseName}
                    </button>
                    {column.build && (
                      <span className="ml-1 text-caption text-ink-weak">{column.build}</span>
                    )}
                  </td>
                  {rowVisible.jockey && (
                    <td className="px-2 py-1.5 text-ink-weak">{column.jockeyName ?? '–'}</td>
                  )}
                  {rowVisible.recent && (
                    <td className="px-2 py-1.5">
                      {column.recentFinishes.length > 0 ? (
                        <span className="flex gap-1.5 tabular-nums">
                          {column.recentFinishes.map((finishPosition, order) => (
                            <span
                              key={`${finishPosition}-${order}`}
                              className={finishClass(finishPosition)}
                            >
                              {finishPosition}
                            </span>
                          ))}
                        </span>
                      ) : (
                        <span className="text-ink-weak">–</span>
                      )}
                    </td>
                  )}
                  {rowVisible.odds && (
                    <td className="px-2 py-1.5 text-right tabular-nums">
                      {column.odds !== null ? column.odds.toFixed(1) : '–'}
                    </td>
                  )}
                  <td className="px-2 py-1.5">
                    <div className="flex items-center justify-end gap-2">
                      <span
                        className={`font-bold tabular-nums ${
                          column.rank === 1 ? 'text-shu' : 'text-ink'
                        }`}
                      >
                        {column.totalScore.toFixed(1)}
                      </span>
                      <ScoreBar
                        totalScore={column.totalScore}
                        rank={column.rank}
                        orientation="horizontal"
                      />
                    </div>
                  </td>
                  {rowVisible.finish && (
                    <td
                      className={`px-2 py-1.5 text-right tabular-nums ${finishClass(column.finishPosition)}`}
                    >
                      {column.finishPosition !== null ? `${column.finishPosition}着` : '–'}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
