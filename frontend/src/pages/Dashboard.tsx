import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Prediction, Race, TopPick } from '../types';
import { apiGet, FETCH_ERROR_MESSAGE, useResource } from '../hooks/useApi';
import { isStaticMode } from '../api/staticRoutes';
import FetchButton from '../components/FetchButton';
import {
  formatPaperDate,
  gradeBadgeClass,
  raceNumberFromId,
  weatherGlyph,
} from '../constants/paper';

/** 日付ごとに並べ替えずグルーピング(API は date 降順で返す) */
function groupByDate(races: Race[]): [string, Race[]][] {
  const grouped = new Map<string, Race[]>();
  for (const race of races) {
    const sameDate = grouped.get(race.date);
    if (sameDate) sameDate.push(race);
    else grouped.set(race.date, [race]);
  }
  return [...grouped.entries()];
}

/**
 * 本紙の◎(予想1位馬)を補う。
 * 静的データ契約では races.json が top_pick を持つので追加取得は起きない。
 * ponytail: API モードは /api/races が top_pick を返さないためレース数ぶんの
 * N+1 になる。重賞のみで件数が小さいので許容。解消するなら
 * バックエンドの RaceOut に top_pick を持たせる。
 */
function useTopPicks(races: Race[]): Record<string, TopPick | null> {
  const [topPicks, setTopPicks] = useState<Record<string, TopPick | null>>({});

  useEffect(() => {
    const missing = races.filter((race) => race.top_pick === undefined);
    if (missing.length === 0) return;

    const controller = new AbortController();
    let cancelled = false;

    Promise.all(
      missing.map(async (race): Promise<[string, TopPick | null]> => {
        try {
          const predictions = await apiGet<Prediction[]>(
            `/races/${race.id}/predictions`,
            controller.signal,
          );
          const top = predictions?.find((prediction) => prediction.rank === 1);
          return [
            race.id,
            top
              ? {
                  horse_id: top.horse_id,
                  horse_name: top.horse_name,
                  total_score: top.total_score,
                }
              : null,
          ];
        } catch {
          return [race.id, null];
        }
      }),
    ).then((pairs) => {
      if (!cancelled) setTopPicks(Object.fromEntries(pairs));
    });

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [races]);

  return topPicks;
}

function RaceRow({ race, topPick }: { race: Race; topPick: TopPick | null | undefined }) {
  const glyph = weatherGlyph(race.weather);
  const raceNumber = raceNumberFromId(race.id);

  return (
    <li className="rule-b">
      <Link
        to={`/race/${race.id}`}
        className="grid grid-cols-[auto_1fr] items-baseline gap-x-3 gap-y-1 px-2 py-2.5
          transition-colors hover:bg-paper-inset sp:grid-cols-[auto_1fr]
          md:grid-cols-[auto_minmax(11rem,16rem)_1fr_auto]"
      >
        <span className={gradeBadgeClass(race.grade)}>{race.grade}</span>

        <span className="font-mincho text-heading font-bold text-ink">{race.name}</span>

        <span className="col-span-2 text-data text-ink-weak md:col-span-1">
          {race.venue}
          {raceNumber ? ` ${raceNumber}` : ''} ・ {race.course_type}
          <span className="tabular-nums">{race.distance}</span>m
          {race.track_condition ? ` ・ ${race.track_condition}` : ''}
          {glyph && <span className="glyph"> {glyph}</span>}
        </span>

        <span className="col-span-2 flex items-baseline gap-1.5 text-data md:col-span-1 md:justify-end">
          {topPick ? (
            <>
              <span className="mark text-shu" aria-label="本命">
                ◎
              </span>
              <span className="font-bold text-ink">{topPick.horse_name}</span>
            </>
          ) : (
            <span className="text-ink-weak">予想未生成</span>
          )}
        </span>
      </Link>
    </li>
  );
}

export default function Dashboard() {
  const { value, status, reload } = useResource<Race[]>('/races');
  const races = value ?? [];
  const topPicks = useTopPicks(races);

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <p className="text-caption text-ink-weak">
          {status === 'ready' && races.length > 0 ? (
            <>
              掲載 <span className="tabular-nums">{races.length}</span> レース
            </>
          ) : (
            '週末の重賞と本紙の見解を載せています'
          )}
        </p>
        <FetchButton onComplete={reload} />
      </div>

      {status === 'loading' && (
        <p className="rule-t py-6 text-center text-data text-ink-weak">
          番組表を読み込んでいます
        </p>
      )}

      {status === 'error' && (
        <p role="alert" className="rule-t py-6 text-center text-data text-shu">
          {FETCH_ERROR_MESSAGE}
        </p>
      )}

      {status === 'ready' && races.length === 0 && (
        <div className="rule-t py-8 text-center">
          <p className="font-mincho text-heading font-bold text-ink">
            次回更新: 土曜 6:00
          </p>
          {!isStaticMode && (
            <p className="mt-1 text-data text-ink-weak">
              手動で取得する場合はデータ取得を実行してください
            </p>
          )}
        </div>
      )}

      {groupByDate(races).map(([date, racesOnDate]) => (
        <section key={date} className="mb-5">
          <h2 className="rule-b py-1.5 font-mincho text-heading font-bold text-ink">
            {formatPaperDate(date)}
          </h2>
          <ul>
            {racesOnDate.map((race) => (
              <RaceRow
                key={race.id}
                race={race}
                topPick={race.top_pick ?? topPicks[race.id]}
              />
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
