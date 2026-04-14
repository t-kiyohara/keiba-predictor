import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Horse, RaceResult } from '../types';
import { useApi } from '../hooks/useApi';
import { TRACK_CONDITION_CLASS, RANK_BADGE } from '../constants/badge';

function calcAge(birthday: string | null): string {
  if (!birthday) return '-';
  const birth = new Date(birthday);
  const today = new Date();
  let age = today.getFullYear() - birth.getFullYear();
  const m = today.getMonth() - birth.getMonth();
  if (m < 0 || (m === 0 && today.getDate() < birth.getDate())) age--;
  return `${age}歳`;
}

/** 直近N走の着順ドットチャート */
function FinishDotChart({ results }: { results: RaceResult[] }) {
  const recent = results.slice(0, 5);
  if (recent.length === 0) return <span className="text-xs text-text-disabled">-</span>;

  return (
    <div className="flex items-end gap-1 h-6">
      {recent.map((r, i) => {
        const pos = r.finish_position;
        const color =
          pos === 1 ? 'bg-yellow-400' :
          pos !== null && pos <= 3 ? 'bg-primary' :
          pos !== null && pos <= 5 ? 'bg-primary/60' :
          'bg-stone-02';
        const heightPx = pos === null ? 4 : Math.max(4, Math.round(24 - (pos - 1) * 3));
        return (
          <div
            key={i}
            title={pos !== null ? `${pos}着` : '不明'}
            className={`w-2.5 rounded-sm transition-all ${color}`}
            style={{ height: `${heightPx}px` }}
          />
        );
      })}
    </div>
  );
}

/** 血統ツリー（簡易版） */
function PedigreeTree({ horse }: { horse: Horse }) {
  const hasPedigree = horse.sire || horse.dam || horse.dam_sire;
  if (!hasPedigree) {
    return <p className="text-sm text-text-disabled">血統情報がありません</p>;
  }

  return (
    <div className="flex items-stretch gap-0">
      {/* 本馬 */}
      <div className="flex items-center">
        <div className="bg-primary/20 border border-primary/40 rounded-lg px-4 py-3 text-center min-w-[120px]">
          <p className="text-xs text-text-grey mb-0.5">本馬</p>
          <p className="font-bold text-sm text-text-black">{horse.name}</p>
        </div>
      </div>

      {/* 接続線 */}
      <div className="flex flex-col justify-center px-2">
        <div className="border-l-2 border-t-2 border-border h-8 w-4 rounded-tl-md"></div>
        <div className="border-l-2 border-b-2 border-border h-8 w-4 rounded-bl-md"></div>
      </div>

      {/* 父・母 */}
      <div className="flex flex-col gap-2 justify-center">
        {horse.sire && (
          <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg px-4 py-2 text-center min-w-[120px]">
            <p className="text-xs text-text-grey mb-0.5">父</p>
            <p className="font-semibold text-sm text-text-black">{horse.sire}</p>
          </div>
        )}
        {horse.dam && (
          <div className="bg-pink-500/10 border border-pink-500/30 rounded-lg px-4 py-2 text-center min-w-[120px]">
            <p className="text-xs text-text-grey mb-0.5">母</p>
            <p className="font-semibold text-sm text-text-black">{horse.dam}</p>
            {horse.dam_sire && (
              <p className="text-xs text-text-disabled mt-0.5">（母父: {horse.dam_sire}）</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function HorseDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [horse, setHorse] = useState<Horse | null>(null);
  const [results, setResults] = useState<RaceResult[]>([]);
  const { fetchApi, loading, error, abort } = useApi();

  useEffect(() => {
    if (!id) return;

    const loadData = async () => {
      const [horseData, resultsData] = await Promise.all([
        fetchApi<Horse>(`/horses/${id}`),
        fetchApi<RaceResult[]>(`/horses/${id}/results`),
      ]);
      if (horseData) setHorse(horseData);
      if (resultsData) setResults(resultsData.slice(0, 10));
    };

    loadData();
    return () => abort();
  }, [id, fetchApi, abort]);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2">
          <div className="skeleton h-8 w-20"></div>
          <div className="skeleton h-4 w-4"></div>
          <div className="skeleton h-4 w-32"></div>
        </div>
        <div className="card-smarthr">
          <div className="p-4 space-y-4">
            <div className="skeleton h-8 w-48"></div>
            <div className="grid grid-cols-2 tablet:grid-cols-3 gap-4">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="space-y-1">
                  <div className="skeleton h-3 w-12"></div>
                  <div className="skeleton h-5 w-24"></div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="alert-error" role="alert">
        <span>{error}</span>
      </div>
    );
  }

  if (!horse) {
    return (
      <div className="alert-warning" role="alert">
        <span>馬の情報が見つかりません。</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* パンくずリスト風ナビゲーション */}
      <div className="flex items-center gap-2 text-sm flex-wrap">
        <button
          className="btn-ghost btn-sm"
          onClick={() => navigate(-1)}
        >
          ← 戻る
        </button>
        <span className="text-text-disabled">/</span>
        <Link to="/" className="text-text-grey hover:text-text-black transition-colors">
          ダッシュボード
        </Link>
        <span className="text-text-disabled">/</span>
        <span className="font-semibold text-text-black">{horse.name}</span>
      </div>

      {/* 馬基本情報 */}
      <div className="card-smarthr">
        <div className="p-4">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-text-black">🐴 {horse.name}</h1>
            {horse.sex && (
              <span className="badge-smarthr border border-border text-text-grey">{horse.sex}</span>
            )}
          </div>
          <div className="grid grid-cols-2 tablet:grid-cols-3 gap-4 mt-4">
            <div>
              <p className="text-sm text-text-grey">性別</p>
              <p className="font-semibold text-text-black">{horse.sex ?? '-'}</p>
            </div>
            <div>
              <p className="text-sm text-text-grey">年齢</p>
              <p className="font-semibold text-text-black">{calcAge(horse.birthday)}</p>
            </div>
            <div>
              <p className="text-sm text-text-grey">生年月日</p>
              <p className="font-semibold text-text-black">{horse.birthday ?? '-'}</p>
            </div>
          </div>
        </div>
      </div>

      {/* 血統ツリー */}
      <div className="card-smarthr">
        <div className="p-4">
          <h2 className="text-xl font-bold mb-4 text-text-black">血統</h2>
          <div className="overflow-x-auto">
            <PedigreeTree horse={horse} />
          </div>
        </div>
      </div>

      {/* 過去成績 */}
      <div>
        <h2 className="text-xl font-bold mb-3 text-text-black">過去成績（直近10走）</h2>
        {results.length > 0 ? (
          <div className="card-smarthr overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-stone-02">
                  <th className="px-3 py-2 text-left text-xs font-semibold text-text-grey whitespace-nowrap">日付</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-text-grey">レース名</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-text-grey">競馬場</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-text-grey">距離</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-text-grey">コース</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-text-grey">馬場</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-text-grey">着順</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-text-grey">タイム</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-text-grey">上り3F</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-text-grey">直近トレンド</th>
                </tr>
              </thead>
              <tbody>
                {results.map((result, idx) => (
                  <tr key={`${result.race_id}-${result.date}`} className="border-t border-border hover:bg-over-bg transition-colors">
                    <td className="px-3 py-2 whitespace-nowrap text-text-black">{result.date}</td>
                    <td className="px-3 py-2 text-text-black">{result.race_name}</td>
                    <td className="px-3 py-2 text-text-black">{result.venue}</td>
                    <td className="px-3 py-2 text-text-black">{result.distance}m</td>
                    <td className="px-3 py-2 text-text-black">{result.course_type}</td>
                    <td className="px-3 py-2">
                      <span className={TRACK_CONDITION_CLASS[result.track_condition] ?? 'badge-smarthr bg-stone-02 text-stone-04'}>
                        {result.track_condition}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      {result.finish_position !== null ? (
                        <span className={RANK_BADGE[result.finish_position] ?? 'badge-smarthr bg-stone-02 text-stone-04'}>
                          {result.finish_position}着
                        </span>
                      ) : '-'}
                    </td>
                    <td className="px-3 py-2 text-text-black">{result.time ?? '-'}</td>
                    <td className="px-3 py-2 text-text-black">{result.last_3f !== null ? result.last_3f.toFixed(1) : '-'}</td>
                    <td className="px-3 py-2">
                      {idx === 0 ? (
                        <FinishDotChart results={results} />
                      ) : (
                        <span className="text-xs text-text-disabled">-</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="alert-info" role="status">
            <span>過去の成績データがありません。</span>
          </div>
        )}
      </div>
    </div>
  );
}
