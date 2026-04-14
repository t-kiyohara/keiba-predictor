import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Race, Prediction } from '../types';
import { useApi } from '../hooks/useApi';
import ScoreTable from '../components/ScoreTable';
import ScoreChart from '../components/ScoreChart';
import WeatherBadge from '../components/WeatherBadge';
import { RANK_BADGE, GRADE_CLASS } from '../constants/badge';

// トップ3カードの背景グラデーション
const RANK_GRADIENT: Record<number, string> = {
  1: 'bg-gradient-to-br from-yellow-500/30 via-amber-400/20 to-yellow-600/10 border border-yellow-500/30',
  2: 'bg-gradient-to-br from-slate-400/30 via-gray-300/20 to-slate-500/10 border border-slate-400/30',
  3: 'bg-gradient-to-br from-amber-700/30 via-orange-600/20 to-amber-800/10 border border-amber-700/30',
};

const RANK_LABEL: Record<number, string> = {
  1: '🥇 1着予想',
  2: '🥈 2着予想',
  3: '🥉 3着予想',
};

const RANK_SCORE_COLOR: Record<number, string> = {
  1: 'text-yellow-600',
  2: 'text-slate-500',
  3: 'text-amber-700',
};

export default function RaceDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [race, setRace] = useState<Race | null>(null);
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [selectedPrediction, setSelectedPrediction] = useState<Prediction | null>(null);
  const { fetchApi, loading, error, abort } = useApi();

  useEffect(() => {
    if (!id) return;

    const loadData = async () => {
      const [raceData, predData] = await Promise.all([
        fetchApi<Race>(`/races/${id}`),
        fetchApi<Prediction[]>(`/races/${id}/predictions`),
      ]);
      if (raceData) setRace(raceData);
      if (predData) {
        setPredictions(predData);
        const top = predData.find((p) => p.rank === 1) ?? null;
        setSelectedPrediction(top);
      }
    };

    loadData();
    return () => abort();
  }, [id, fetchApi, abort]);

  const handleHorseSelect = (horseId: string) => {
    const pred = predictions.find((p) => p.horse_id === horseId) ?? null;
    setSelectedPrediction(pred);
  };

  // ローディング中スケルトン
  if (loading) {
    return (
      <div className="space-y-6">
        <div className="skeleton h-8 w-32"></div>
        <div className="card-smarthr">
          <div className="p-4 space-y-4">
            <div className="skeleton h-8 w-64"></div>
            <div className="grid grid-cols-2 desktop:grid-cols-4 gap-4">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="space-y-2">
                  <div className="skeleton h-3 w-16"></div>
                  <div className="skeleton h-5 w-24"></div>
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="grid grid-cols-1 tablet:grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="card-smarthr">
              <div className="p-4 space-y-3">
                <div className="skeleton h-5 w-20"></div>
                <div className="skeleton h-7 w-32"></div>
                <div className="skeleton h-4 w-28"></div>
              </div>
            </div>
          ))}
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

  if (!race) {
    return (
      <div className="alert-warning" role="alert">
        <span>レース情報が見つかりません。</span>
      </div>
    );
  }

  const top3 = predictions.filter((p) => p.rank <= 3);

  return (
    <div className="space-y-6">
      {/* パンくずリスト風ナビゲーション */}
      <div className="flex items-center gap-2 text-sm">
        <button
          className="btn-ghost btn-sm"
          onClick={() => navigate('/')}
        >
          ← 一覧に戻る
        </button>
        <span className="text-text-disabled">/</span>
        <span className="text-text-grey">ダッシュボード</span>
        <span className="text-text-disabled">/</span>
        <span className="font-semibold text-text-black truncate max-w-xs">{race.name}</span>
      </div>

      {/* レース基本情報 */}
      <div className="card-smarthr">
        <div className="p-4">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl font-bold text-text-black">{race.name}</h1>
            {race.grade && (
              <span className={GRADE_CLASS[race.grade] ?? 'badge-smarthr bg-stone-02 text-stone-04'}>
                {race.grade}
              </span>
            )}
          </div>
          <div className="grid grid-cols-2 desktop:grid-cols-4 gap-4 mt-4">
            <div>
              <p className="text-sm text-text-grey">日付</p>
              <p className="font-semibold text-text-black">{race.date}</p>
            </div>
            <div>
              <p className="text-sm text-text-grey">競馬場</p>
              <p className="font-semibold text-text-black">{race.venue}</p>
            </div>
            <div>
              <p className="text-sm text-text-grey">距離・コース</p>
              <p className="font-semibold text-text-black">{race.course_type} {race.distance}m</p>
            </div>
            <div>
              <p className="text-sm text-text-grey">天気・馬場</p>
              <WeatherBadge weather={race.weather} trackCondition={race.track_condition} />
            </div>
          </div>
        </div>
      </div>

      {/* トップ3ハイライト */}
      {top3.length > 0 && (
        <div>
          <h2 className="text-xl font-bold mb-3 text-text-black">予想上位馬</h2>
          <div className="grid grid-cols-1 tablet:grid-cols-3 gap-4">
            {top3.map((pred) => (
              <div
                key={pred.horse_id}
                className={`rounded-lg cursor-pointer hover:scale-[1.02] transition-all duration-200 ${RANK_GRADIENT[pred.rank] ?? 'card-smarthr'}`}
                onClick={() => setSelectedPrediction(pred)}
              >
                <div className="p-4">
                  <div className="flex items-center gap-2">
                    <span className={RANK_BADGE[pred.rank] ?? 'badge-smarthr bg-stone-02 text-stone-04'}>
                      {RANK_LABEL[pred.rank] ?? `${pred.rank}着`}
                    </span>
                  </div>
                  <div className="flex items-end justify-between mt-2">
                    <div>
                      <p className="text-lg font-bold text-text-black">{pred.horse_name}</p>
                      <Link
                        to={`/horse/${pred.horse_id}`}
                        className="text-xs text-primary hover:underline"
                        onClick={(e) => e.stopPropagation()}
                      >
                        詳細 →
                      </Link>
                    </div>
                    <p className={`text-2xl font-black ${RANK_SCORE_COLOR[pred.rank] ?? 'text-text-grey'}`}>
                      {pred.total_score.toFixed(1)}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* スコアテーブルとチャート */}
      {predictions.length > 0 && (
        <div className="grid grid-cols-1 desktop:grid-cols-3 gap-6">
          <div className="desktop:col-span-2">
            <h2 className="text-xl font-bold mb-3 text-text-black">全馬ランキング</h2>
            <div className="card-smarthr p-2">
              <ScoreTable
                predictions={predictions}
                selectedHorseId={selectedPrediction?.horse_id ?? null}
                onHorseClick={(horseId) => handleHorseSelect(horseId)}
              />
            </div>
            <p className="text-xs text-text-disabled mt-2 text-center">
              行をクリックするとチャートが切り替わります
            </p>
          </div>
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-xl font-bold text-text-black">ファクター別スコア</h2>
              {selectedPrediction && (
                <Link
                  to={`/horse/${selectedPrediction.horse_id}`}
                  className="btn-secondary btn-sm text-xs"
                >
                  馬詳細 →
                </Link>
              )}
            </div>
            <ScoreChart prediction={selectedPrediction} />
          </div>
        </div>
      )}

      {predictions.length === 0 && (
        <div className="alert-info" role="status">
          <span>このレースの予想データはまだありません。</span>
        </div>
      )}
    </div>
  );
}
