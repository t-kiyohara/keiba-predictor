import { Link, useParams } from 'react-router-dom';
import { Horse, RaceResult } from '../types';
import { FETCH_ERROR_MESSAGE, useResource } from '../hooks/useApi';
import {
  finishClass,
  formatPaperDate,
  gradeBadgeClass,
  splitRaceName,
} from '../constants/paper';

function calcAge(birthday: string | null): string {
  if (!birthday) return '–';
  const [year, month, day] = birthday.split('-').map(Number);
  if (!year || !month || !day) return '–';
  const today = new Date();
  let age = today.getFullYear() - year;
  if (
    today.getMonth() + 1 < month ||
    (today.getMonth() + 1 === month && today.getDate() < day)
  ) {
    age -= 1;
  }
  return `${age}歳`;
}

function Pedigree({ horse }: { horse: Horse }) {
  const lines: [string, string | null][] = [
    ['父', horse.sire],
    ['母', horse.dam],
    ['母父', horse.dam_sire],
  ];
  if (lines.every(([, name]) => !name)) {
    return <p className="text-data text-ink-weak">血統情報は未取得です</p>;
  }

  return (
    <dl className="max-w-md text-data">
      {lines.map(([label, name]) => (
        <div key={label} className="rule-b flex gap-3 py-1">
          <dt className="w-12 shrink-0 text-ink-weak">{label}</dt>
          <dd className="text-ink">{name ?? '–'}</dd>
        </div>
      ))}
    </dl>
  );
}

export default function HorseDetail() {
  const { id } = useParams<{ id: string }>();
  const horseResource = useResource<Horse>(id ? `/horses/${id}` : null);
  const resultResource = useResource<RaceResult[]>(
    id ? `/horses/${id}/results` : null,
  );

  const horse = horseResource.value;
  const results = resultResource.value ?? [];
  // 静的データ契約のみが持つ列(グレード・着差・騎手)。API モードでは列自体を出さない
  const hasRaceDetail = results.some(
    (result) => result.grade || result.margin || result.jockey_name,
  );

  return (
    <div>
      <p className="mb-2 text-caption">
        <Link to="/" className="link-ai">
          番組表へ戻る
        </Link>
      </p>

      {/* 馬の見出し欄 */}
      <div className="rule-heavy pb-2">
        {horseResource.status === 'loading' && (
          <p className="py-2 text-data text-ink-weak">
            馬の情報を読み込んでいます
          </p>
        )}
        {horseResource.status === 'error' && (
          <p role="alert" className="py-2 text-data text-shu">
            馬の情報を取得できませんでした。時間をおいて再実行してください
          </p>
        )}
        {horse && (
          <>
            <h1 className="font-mincho text-race-name font-bold text-ink">
              {horse.name}
            </h1>
            {/* プロフィール未取得の馬(過去結果だけの馬)では「不明」を並べず行ごと省く */}
            {(horse.sex || horse.birthday) && (
              <p className="mt-0.5 text-data text-ink-weak">
                {horse.sex && <span>{horse.sex}</span>}
                {horse.sex && horse.birthday && ' ・ '}
                {horse.birthday && (
                  <>
                    {calcAge(horse.birthday)} ・ 生年月日{' '}
                    <span className="tabular-nums">{horse.birthday}</span>
                  </>
                )}
              </p>
            )}
          </>
        )}
      </div>

      {/* 血統欄 */}
      {horse && (
        <section className="rule-b py-3">
          <h2 className="mb-2 font-mincho text-heading font-bold text-ink">
            血統
          </h2>
          <Pedigree horse={horse} />
        </section>
      )}

      {/* 戦績欄 */}
      <section className="py-3">
        <h2 className="mb-2 font-mincho text-heading font-bold text-ink">
          戦績
        </h2>

        {resultResource.status === 'loading' && (
          <p className="text-data text-ink-weak">戦績を読み込んでいます</p>
        )}
        {resultResource.status === 'error' && (
          <p role="alert" className="text-data text-shu">
            {FETCH_ERROR_MESSAGE}
          </p>
        )}
        {resultResource.status === 'ready' && results.length === 0 && (
          <p className="text-data text-ink-weak">
            戦績はまだ取得できていません
          </p>
        )}

        {results.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-data">
              <caption className="sr-only">過去の戦績</caption>
              <thead>
                <tr className="bg-paper-inset text-left text-caption text-ink-weak">
                  <th
                    scope="col"
                    className="whitespace-nowrap px-2 py-1 font-medium"
                  >
                    日付
                  </th>
                  <th scope="col" className="px-2 py-1 font-medium">
                    レース
                  </th>
                  <th scope="col" className="px-2 py-1 font-medium">
                    競馬場
                  </th>
                  <th scope="col" className="px-2 py-1 font-medium">
                    コース
                  </th>
                  <th scope="col" className="px-2 py-1 font-medium">
                    馬場
                  </th>
                  {hasRaceDetail && (
                    <th scope="col" className="px-2 py-1 font-medium">
                      騎手
                    </th>
                  )}
                  <th scope="col" className="px-2 py-1 text-right font-medium">
                    着順
                  </th>
                  {hasRaceDetail && (
                    <th
                      scope="col"
                      className="px-2 py-1 text-right font-medium"
                    >
                      着差
                    </th>
                  )}
                  <th scope="col" className="px-2 py-1 text-right font-medium">
                    タイム
                  </th>
                  <th scope="col" className="px-2 py-1 text-right font-medium">
                    上がり3F
                  </th>
                </tr>
              </thead>
              <tbody>
                {results.map((result) => (
                  <tr
                    key={`${result.race_id}-${result.date}`}
                    className="border-t border-rule transition-colors hover:bg-paper-inset"
                  >
                    <td className="whitespace-nowrap px-2 py-1.5 tabular-nums text-ink-weak">
                      {formatPaperDate(result.date)}
                    </td>
                    <td className="px-2 py-1.5">
                      <span className="font-mincho font-bold text-ink">
                        {splitRaceName(result.race_name).title}
                      </span>
                      {result.grade && (
                        <span
                          className={`ml-1.5 ${gradeBadgeClass(result.grade)}`}
                        >
                          {result.grade}
                        </span>
                      )}
                    </td>
                    <td className="px-2 py-1.5 text-ink">{result.venue}</td>
                    <td className="whitespace-nowrap px-2 py-1.5 text-ink">
                      {result.course_type}
                      <span className="tabular-nums">{result.distance}</span>m
                    </td>
                    <td className="px-2 py-1.5 text-ink">
                      {result.track_condition ?? '–'}
                    </td>
                    {hasRaceDetail && (
                      <td className="px-2 py-1.5 text-ink-weak">
                        {result.jockey_name ?? '–'}
                      </td>
                    )}
                    <td
                      className={`px-2 py-1.5 text-right tabular-nums ${finishClass(result.finish_position)}`}
                    >
                      {result.finish_position !== null
                        ? `${result.finish_position}着`
                        : '–'}
                    </td>
                    {hasRaceDetail && (
                      <td className="px-2 py-1.5 text-right text-ink-weak">
                        {result.margin ?? '–'}
                      </td>
                    )}
                    <td className="px-2 py-1.5 text-right tabular-nums text-ink">
                      {result.time ?? '–'}
                    </td>
                    <td className="px-2 py-1.5 text-right tabular-nums text-ink">
                      {result.last_3f !== null
                        ? result.last_3f.toFixed(1)
                        : '–'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
