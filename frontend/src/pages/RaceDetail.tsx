import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Entry, Prediction, Race } from '../types';
import { FETCH_ERROR_MESSAGE, useResource } from '../hooks/useApi';
import Umabashira from '../components/Umabashira';
import {
  formatPaperDateFull,
  gradeBadgeClass,
  markColorClass,
  markForRank,
  MARK_LEGEND,
  raceNumberFromId,
  weatherGlyph,
} from '../constants/paper';

/** 選択馬の8ファクター内訳。Chart.js レーダーではなく CSS 横バー(DESIGN.md §5-2) */
function FactorBars({ prediction }: { prediction: Prediction }) {
  const factors = Object.entries(prediction.factor_scores);

  return (
    <div className="space-y-1.5">
      {factors.map(([key, factor]) => (
        <div
          key={key}
          className="grid grid-cols-[7rem_1fr_auto] items-center gap-x-3 sp:grid-cols-[5.5rem_1fr_auto]"
        >
          <span className="text-data text-ink">{factor.label}</span>
          <span className="h-2 w-full bg-rule" aria-hidden="true">
            <span
              className="block h-full bg-ink"
              style={{ width: `${Math.min(100, Math.max(0, factor.score))}%` }}
            />
          </span>
          <span className="text-data tabular-nums text-ink">
            {factor.score.toFixed(1)}
            <span className="ml-1.5 text-caption text-ink-weak">
              寄与 {factor.weighted.toFixed(1)}
            </span>
          </span>
        </div>
      ))}
    </div>
  );
}

/** ◎○▲△の馬と総合スコアの順位表(DESIGN.md §5-2) */
function MarkRanking({
  predictions,
  onSelect,
}: {
  predictions: Prediction[];
  onSelect: (horseId: string) => void;
}) {
  const marked = predictions.filter((prediction) => markForRank(prediction.rank) !== null);
  if (marked.length === 0) return null;

  return (
    <table className="w-full max-w-md border-collapse text-data">
      <caption className="sr-only">本紙の印と総合スコア</caption>
      <thead>
        <tr className="bg-paper-inset text-left text-caption text-ink-weak">
          <th scope="col" className="px-2 py-1 font-medium">
            印
          </th>
          <th scope="col" className="px-2 py-1 font-medium">
            馬名
          </th>
          <th scope="col" className="px-2 py-1 text-right font-medium">
            総合スコア
          </th>
          <th scope="col" className="px-2 py-1 text-right font-medium">
            戦績
          </th>
        </tr>
      </thead>
      <tbody>
        {marked.map((prediction) => {
          const mark = markForRank(prediction.rank);
          return (
            <tr key={prediction.horse_id} className="border-t border-rule">
              <td className="px-2 py-1.5">
                <span
                  className={`mark ${markColorClass(prediction.rank)}`}
                  role="img"
                  aria-label={mark?.label ?? ''}
                >
                  {mark?.symbol}
                </span>
              </td>
              <td className="px-2 py-1.5">
                <button
                  type="button"
                  onClick={() => onSelect(prediction.horse_id)}
                  className="text-left font-mincho font-bold text-ink"
                >
                  {prediction.horse_name}
                </button>
              </td>
              <td className="px-2 py-1.5 text-right font-bold tabular-nums">
                {prediction.total_score.toFixed(1)}
              </td>
              <td className="px-2 py-1.5 text-right">
                <Link to={`/horse/${prediction.horse_id}`} className="link-ai text-caption">
                  見る
                </Link>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export default function RaceDetail() {
  const { id } = useParams<{ id: string }>();
  const [selectedHorseId, setSelectedHorseId] = useState<string | null>(null);

  // 欄ごとに独立して読む。片方が失敗しても他の欄は描画する
  const raceResource = useResource<Race>(id ? `/races/${id}` : null);
  const predictionResource = useResource<Prediction[]>(id ? `/races/${id}/predictions` : null);
  // 出走馬(枠色・馬番・オッズ・騎手)。未実装のバックエンドでは 404 になるので欠損扱い
  const entryResource = useResource<Entry[]>(id ? `/races/${id}/entries` : null);

  const race = raceResource.value;
  const predictions = predictionResource.value ?? [];
  const entries = entryResource.value ?? [];

  const selected =
    predictions.find((prediction) => prediction.horse_id === selectedHorseId) ??
    predictions.find((prediction) => prediction.rank === 1) ??
    null;

  const glyph = race ? weatherGlyph(race.weather) : null;
  const raceNumber = race ? raceNumberFromId(race.id) : null;

  return (
    <div>
      <p className="mb-2 text-caption">
        <Link to="/" className="link-ai">
          番組表へ戻る
        </Link>
      </p>

      {/* レース見出し欄 */}
      <div className="rule-heavy pb-2">
        {raceResource.status === 'loading' && (
          <p className="py-2 text-data text-ink-weak">レース情報を読み込んでいます</p>
        )}
        {raceResource.status === 'error' && (
          <p role="alert" className="py-2 text-data text-shu">
            レース情報を取得できませんでした。時間をおいて再実行してください
          </p>
        )}
        {race && (
          <>
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
              <h1 className="flex flex-wrap items-center gap-2">
                <span className={gradeBadgeClass(race.grade)}>{race.grade}</span>
                <span className="font-mincho text-race-name font-bold text-ink">
                  {race.name}
                </span>
              </h1>
              <p className="text-data text-ink-weak">
                {formatPaperDateFull(race.date)} {race.venue}
                {raceNumber ? ` ${raceNumber}` : ''}
              </p>
            </div>
            <p className="mt-0.5 text-data text-ink">
              {race.course_type}
              <span className="tabular-nums">{race.distance}</span>m ・{' '}
              {race.track_condition ?? '馬場未発表'} ・ {race.weather ?? '天候未発表'}
              {glyph && <span className="glyph"> {glyph}</span>}
            </p>
          </>
        )}
      </div>

      {/* 馬柱欄 */}
      <section className="rule-b py-3">
        {predictionResource.status === 'loading' && (
          <p className="text-data text-ink-weak">馬柱を組んでいます</p>
        )}
        {predictionResource.status === 'error' && (
          <p role="alert" className="text-data text-shu">
            {FETCH_ERROR_MESSAGE}
          </p>
        )}
        {predictionResource.status === 'ready' && predictions.length === 0 && (
          <p className="text-data text-ink-weak">
            このレースの予想はまだ組まれていません。データ取得を実行すると生成されます
          </p>
        )}
        {predictions.length > 0 && (
          <>
            <Umabashira
              predictions={predictions}
              entries={entries}
              selectedHorseId={selected?.horse_id ?? null}
              onSelect={setSelectedHorseId}
            />
            {entryResource.status !== 'loading' && entries.length === 0 && (
              <p className="mt-2 text-caption text-ink-weak">
                出走馬の枠順・オッズ・騎手は未取得です(予想順に並べています)
              </p>
            )}
          </>
        )}
      </section>

      {/* ファクター欄 */}
      {selected && (
        <section className="rule-b py-3">
          <h2 className="mb-2 flex flex-wrap items-baseline gap-2">
            <span className="font-mincho text-heading font-bold text-ink">
              {selected.horse_name}
            </span>
            <span className="text-caption text-ink-weak">
              総合スコア{' '}
              <span className="tabular-nums font-bold text-ink">
                {selected.total_score.toFixed(1)}
              </span>
              {' ・ 予想 '}
              <span className="tabular-nums">{selected.rank}</span>位
            </span>
            <Link to={`/horse/${selected.horse_id}`} className="link-ai text-caption">
              戦績を見る
            </Link>
          </h2>
          <FactorBars prediction={selected} />
          <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-caption text-ink-weak">
            {MARK_LEGEND.map((legend) => (
              <li key={legend.symbol}>
                <span className={legend.symbol === '◎' ? 'text-shu' : 'text-ink'}>
                  {legend.symbol}
                </span>{' '}
                {legend.label}({legend.note})
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* 印一覧 */}
      {predictions.length > 0 && (
        <section className="py-3">
          <h2 className="mb-2 font-mincho text-heading font-bold text-ink">印一覧</h2>
          <MarkRanking predictions={predictions} onSelect={setSelectedHorseId} />
        </section>
      )}
    </div>
  );
}
