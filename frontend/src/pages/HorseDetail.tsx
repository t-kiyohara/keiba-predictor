import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Horse, RaceResult } from '../types';
import { useApi } from '../hooks/useApi';

const TRACK_CONDITION_CLASS: Record<string, string> = {
  良: 'badge-success',
  稍重: 'badge-warning',
  重: 'badge-error',
  不良: 'badge-error',
};

function calcAge(birthday: string | null): string {
  if (!birthday) return '-';
  const birth = new Date(birthday);
  const today = new Date();
  let age = today.getFullYear() - birth.getFullYear();
  const m = today.getMonth() - birth.getMonth();
  if (m < 0 || (m === 0 && today.getDate() < birth.getDate())) age--;
  return `${age}歳`;
}

export default function HorseDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [horse, setHorse] = useState<Horse | null>(null);
  const [results, setResults] = useState<RaceResult[]>([]);
  const { fetchApi, loading, error } = useApi();

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
  }, [id, fetchApi]);

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <span className="loading loading-spinner loading-lg"></span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="alert alert-error">
        <span>{error}</span>
      </div>
    );
  }

  if (!horse) {
    return (
      <div className="alert alert-warning">
        <span>馬の情報が見つかりません。</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 戻るボタン */}
      <button className="btn btn-ghost btn-sm" onClick={() => navigate(-1)}>
        ← 戻る
      </button>

      {/* 馬基本情報 */}
      <div className="card bg-base-100 shadow-lg">
        <div className="card-body">
          <h1 className="card-title text-2xl">{horse.name}</h1>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mt-4">
            <div>
              <p className="text-sm opacity-60">性別</p>
              <p className="font-semibold">{horse.sex ?? '-'}</p>
            </div>
            <div>
              <p className="text-sm opacity-60">年齢</p>
              <p className="font-semibold">{calcAge(horse.birthday)}</p>
            </div>
            <div>
              <p className="text-sm opacity-60">生年月日</p>
              <p className="font-semibold">{horse.birthday ?? '-'}</p>
            </div>
            <div>
              <p className="text-sm opacity-60">父</p>
              <p className="font-semibold">{horse.sire ?? '-'}</p>
            </div>
            <div>
              <p className="text-sm opacity-60">母</p>
              <p className="font-semibold">{horse.dam ?? '-'}</p>
            </div>
            <div>
              <p className="text-sm opacity-60">母父</p>
              <p className="font-semibold">{horse.dam_sire ?? '-'}</p>
            </div>
          </div>
        </div>
      </div>

      {/* 過去成績 */}
      <div>
        <h2 className="text-xl font-bold mb-3">過去成績（直近10走）</h2>
        {results.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="table table-zebra w-full">
              <thead>
                <tr>
                  <th>日付</th>
                  <th>レース名</th>
                  <th>競馬場</th>
                  <th>距離</th>
                  <th>コース</th>
                  <th>馬場</th>
                  <th>着順</th>
                  <th>タイム</th>
                  <th>上り3F</th>
                </tr>
              </thead>
              <tbody>
                {results.map((result) => (
                  <tr key={`${result.race_id}-${result.date}`}>
                    <td className="whitespace-nowrap">{result.date}</td>
                    <td>{result.race_name}</td>
                    <td>{result.venue}</td>
                    <td>{result.distance}m</td>
                    <td>{result.course_type}</td>
                    <td>
                      <span className={`badge badge-sm ${TRACK_CONDITION_CLASS[result.track_condition] ?? 'badge-neutral'}`}>
                        {result.track_condition}
                      </span>
                    </td>
                    <td>
                      {result.finish_position !== null ? (
                        <span className={`badge ${result.finish_position === 1 ? 'badge-warning' : result.finish_position <= 3 ? 'badge-accent' : 'badge-neutral'}`}>
                          {result.finish_position}着
                        </span>
                      ) : '-'}
                    </td>
                    <td>{result.time ?? '-'}</td>
                    <td>{result.last_3f !== null ? result.last_3f.toFixed(1) : '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="alert alert-info">
            <span>過去の成績データがありません。</span>
          </div>
        )}
      </div>
    </div>
  );
}
