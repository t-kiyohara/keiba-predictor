import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Race, Prediction } from '../types';
import { useApi } from '../hooks/useApi';
import ScoreTable from '../components/ScoreTable';
import ScoreChart from '../components/ScoreChart';
import WeatherBadge from '../components/WeatherBadge';

const RANK_BADGE: Record<number, string> = {
  1: 'badge-warning',   // gold
  2: 'badge-ghost',     // silver
  3: 'badge-accent',    // bronze
};

const RANK_LABEL: Record<number, string> = {
  1: '🥇 1着',
  2: '🥈 2着',
  3: '🥉 3着',
};

export default function RaceDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [race, setRace] = useState<Race | null>(null);
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [selectedPrediction, setSelectedPrediction] = useState<Prediction | null>(null);
  const { fetchApi, loading, error } = useApi();

  useEffect(() => {
    if (!id) return;

    const loadData = async () => {
      const [raceData, predData] = await Promise.all([
        fetchApi<Race>(`/races/${id}`),
        fetchApi<Prediction[]>(`/races/${id}/predictions`),
      ]);
      if (raceData) setRace(raceData);
      if (predData) setPredictions(predData);
    };

    loadData();
  }, [id, fetchApi]);

  const handleHorseClick = (horseId: string) => {
    navigate(`/horse/${horseId}`);
  };

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

  if (!race) {
    return (
      <div className="alert alert-warning">
        <span>レース情報が見つかりません。</span>
      </div>
    );
  }

  const top3 = predictions.filter((p) => p.rank <= 3);

  return (
    <div className="space-y-6">
      {/* 戻るボタン */}
      <button className="btn btn-ghost btn-sm" onClick={() => navigate('/')}>
        ← 一覧に戻る
      </button>

      {/* レース基本情報 */}
      <div className="card bg-base-100 shadow-lg">
        <div className="card-body">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="card-title text-2xl">{race.name}</h1>
            {race.grade && (
              <span className={`badge ${race.grade === 'G1' ? 'badge-error' : race.grade === 'G2' ? 'badge-warning' : 'badge-success'} badge-lg`}>
                {race.grade}
              </span>
            )}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
            <div>
              <p className="text-sm opacity-60">日付</p>
              <p className="font-semibold">{race.date}</p>
            </div>
            <div>
              <p className="text-sm opacity-60">競馬場</p>
              <p className="font-semibold">{race.venue}</p>
            </div>
            <div>
              <p className="text-sm opacity-60">距離・コース</p>
              <p className="font-semibold">{race.course_type} {race.distance}m</p>
            </div>
            <div>
              <p className="text-sm opacity-60">天気・馬場</p>
              <WeatherBadge weather={race.weather} trackCondition={race.track_condition} />
            </div>
          </div>
        </div>
      </div>

      {/* トップ3ハイライト */}
      {top3.length > 0 && (
        <div>
          <h2 className="text-xl font-bold mb-3">予想上位馬</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {top3.map((pred) => (
              <div
                key={pred.horse_id}
                className="card bg-base-100 shadow cursor-pointer hover:shadow-lg transition-shadow"
                onClick={() => handleHorseClick(pred.horse_id)}
              >
                <div className="card-body">
                  <div className="flex items-center gap-2">
                    <span className={`badge ${RANK_BADGE[pred.rank] ?? 'badge-neutral'}`}>
                      {RANK_LABEL[pred.rank] ?? `${pred.rank}着`}
                    </span>
                  </div>
                  <p className="text-lg font-bold mt-2">{pred.horse_name}</p>
                  <p className="text-sm opacity-70">総合スコア: {pred.total_score.toFixed(1)}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* スコアテーブルとチャート */}
      {predictions.length > 0 && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          <div className="xl:col-span-2">
            <h2 className="text-xl font-bold mb-3">全馬ランキング</h2>
            <ScoreTable
              predictions={predictions}
              onHorseClick={(horseId) => {
                const pred = predictions.find((p) => p.horse_id === horseId) ?? null;
                setSelectedPrediction(pred);
              }}
            />
          </div>
          <div>
            <h2 className="text-xl font-bold mb-3">ファクター別スコア</h2>
            <ScoreChart prediction={selectedPrediction} />
          </div>
        </div>
      )}

      {predictions.length === 0 && (
        <div className="alert alert-info">
          <span>このレースの予想データはまだありません。</span>
        </div>
      )}
    </div>
  );
}
