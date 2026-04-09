import { useState, useEffect, useCallback } from 'react';
import { Race } from '../types';
import { useApi } from '../hooks/useApi';
import RaceCard from '../components/RaceCard';
import FetchButton from '../components/FetchButton';

export default function Dashboard() {
  const [races, setRaces] = useState<Race[]>([]);
  const { fetchApi, loading, error } = useApi();

  const loadRaces = useCallback(async () => {
    const data = await fetchApi<Race[]>('/races');
    if (data) {
      setRaces(data);
    }
  }, [fetchApi]);

  useEffect(() => {
    loadRaces();
  }, [loadRaces]);

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

      {/* ローディング中 - スケルトン表示 */}
      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="card bg-base-100 shadow">
              <div className="card-body gap-3">
                <div className="skeleton h-6 w-3/4"></div>
                <div className="skeleton h-4 w-1/2"></div>
                <div className="skeleton h-4 w-2/3"></div>
                <div className="flex justify-end">
                  <div className="skeleton h-8 w-24"></div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* レース一覧 */}
      {!loading && races.length > 0 && (
        <div>
          <h2 className="text-xl font-semibold mb-4">レース一覧 ({races.length}件)</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {races.map((race) => (
              <RaceCard key={race.id} race={race} />
            ))}
          </div>
        </div>
      )}

      {/* データなし - hero コンポーネント */}
      {!loading && races.length === 0 && !error && (
        <div className="hero min-h-[50vh] bg-base-100 rounded-2xl shadow">
          <div className="hero-content text-center">
            <div className="max-w-md">
              <div className="text-8xl mb-6">🏇</div>
              <h2 className="text-3xl font-bold mb-4">レースデータがありません</h2>
              <p className="text-base opacity-70 mb-6">
                右上の「データ取得」ボタンを押してレース情報を取得してください。<br />
                取得完了後、最新のレース予想をご確認いただけます。
              </p>
              <div className="flex flex-col gap-2 text-sm opacity-50">
                <div className="flex items-center justify-center gap-2">
                  <span className="badge badge-outline">Step 1</span>
                  <span>「データ取得」ボタンをクリック</span>
                </div>
                <div className="flex items-center justify-center gap-2">
                  <span className="badge badge-outline">Step 2</span>
                  <span>データ取得完了を待機</span>
                </div>
                <div className="flex items-center justify-center gap-2">
                  <span className="badge badge-outline">Step 3</span>
                  <span>レース一覧から予想を確認</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
