import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
} from 'chart.js';
import { Radar } from 'react-chartjs-2';
import { Prediction } from '../types';

ChartJS.register(
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
);

interface Props {
  prediction: Prediction | null;
}

export default function ScoreChart({ prediction }: Props) {
  if (!prediction) {
    return (
      <div className="card bg-base-100 shadow flex items-center justify-center" style={{ minHeight: '300px' }}>
        <div className="text-center opacity-50">
          <div className="text-5xl mb-3">📊</div>
          <p className="text-lg">馬を選択してください</p>
          <p className="text-sm mt-1">ランキング表の馬名をクリック</p>
        </div>
      </div>
    );
  }

  const factorEntries = Object.entries(prediction.factor_scores);
  const labels = factorEntries.map(([, fs]) => fs.label);
  const scores = factorEntries.map(([, fs]) => fs.score);
  const weightedScores = factorEntries.map(([, fs]) => fs.weighted);

  const data = {
    labels,
    datasets: [
      {
        label: prediction.horse_name,
        data: scores,
        backgroundColor: 'rgba(99, 102, 241, 0.15)',
        borderColor: 'rgba(99, 102, 241, 0.9)',
        borderWidth: 2,
        pointBackgroundColor: 'rgba(99, 102, 241, 1)',
        pointBorderColor: 'rgba(30, 30, 46, 1)',
        pointBorderWidth: 2,
        pointRadius: 4,
        pointHoverRadius: 6,
        pointHoverBackgroundColor: '#fff',
        pointHoverBorderColor: 'rgba(99, 102, 241, 1)',
      },
    ],
  };

  const options = {
    responsive: true,
    scales: {
      r: {
        min: 0,
        max: 100,
        ticks: {
          stepSize: 25,
          color: 'rgba(156, 163, 175, 0.6)',
          backdropColor: 'transparent',
          font: { size: 9 },
        },
        grid: {
          color: 'rgba(156, 163, 175, 0.15)',
          lineWidth: 1,
        },
        pointLabels: {
          color: 'rgba(209, 213, 219, 0.85)',
          font: { size: 11, weight: 'bold' as const },
        },
        angleLines: {
          color: 'rgba(156, 163, 175, 0.15)',
        },
      },
    },
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        backgroundColor: 'rgba(15, 15, 30, 0.9)',
        titleColor: 'rgba(209, 213, 219, 1)',
        bodyColor: 'rgba(156, 163, 175, 1)',
        borderColor: 'rgba(99, 102, 241, 0.5)',
        borderWidth: 1,
        callbacks: {
          label: (context: { dataset: { label?: string }; parsed: { r: number } }) => {
            return `スコア: ${context.parsed.r.toFixed(1)}`;
          },
        },
      },
    },
  };

  // スコアの最大値を基準にパーセント表示
  const maxScore = Math.max(...weightedScores, 1);

  return (
    <div className="card bg-base-100 shadow p-4 space-y-4">
      <div className="text-center">
        <h3 className="font-bold text-base">{prediction.horse_name}</h3>
        <p className="text-xs opacity-50 mt-0.5">総合スコア: {prediction.total_score.toFixed(1)}</p>
      </div>

      <Radar data={data} options={options} />

      {/* ファクター別スコアリスト */}
      <div className="space-y-2 pt-2 border-t border-base-200">
        <p className="text-xs font-semibold opacity-60 uppercase tracking-wider">ファクター詳細</p>
        {factorEntries.map(([key, fs]) => {
          const pct = Math.min(100, (fs.weighted / maxScore) * 100);
          return (
            <div key={key} className="space-y-0.5">
              <div className="flex justify-between text-xs">
                <span className="opacity-80">{fs.label}</span>
                <span className="font-mono font-semibold opacity-90">{fs.weighted.toFixed(1)}</span>
              </div>
              <div className="w-full bg-base-200 rounded-full h-1.5">
                <div
                  className="h-1.5 rounded-full bg-primary transition-all duration-500"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
