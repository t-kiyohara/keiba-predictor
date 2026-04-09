import { useState, useEffect } from 'react';
import { Race } from '../types';
import { useApi } from '../hooks/useApi';
import RaceCard from '../components/RaceCard';
import FetchButton from '../components/FetchButton';

export default function Dashboard() {
  const [races, setRaces] = useState<Race[]>([]);
  const { fetchApi, loading, error } = useApi();

  const loadRaces = async () => {
    const data = await fetchApi<Race[]>('/races');
    if (data) {
      setRaces(data);
    }
  };

  useEffect(() => {
    loadRaces();
  }, [fetchApi]);

  return (
    <div className="space-y-6">
      {/* ページタイトル */}
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">ダッシュボード</h1>
        <FetchButton onComplete={loadRaces} />
      </div>

      {/* エラー表示 */}
      {error && (
        <div className="alert alert-error">
          <svg xmlns="http://www.w3.org/2000/svg" className="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>{error}</span>
        </div>
      )}

      {/* ローディング中 */}
      {loading && (
        <div className="flex justify-center py-12">
          <span className="loading loading-spinner loading-lg"></span>
        </div>
      )}

      {/* レース一覧 */}
      {!loading && races.length > 0 && (
        <div>
          <h2 className="text-xl font-semibold mb-4">レース一覧 ({races.length}件)</h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {races.map((race) => (
              <RaceCard key={race.id} race={race} />
            ))}
          </div>
        </div>
      )}

      {/* データなし */}
      {!loading && races.length === 0 && !error && (
        <div className="alert alert-info">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" className="stroke-current shrink-0 w-6 h-6">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
          </svg>
          <span>データ取得ボタンを押してレース情報を取得してください。</span>
        </div>
      )}
    </div>
  );
}
