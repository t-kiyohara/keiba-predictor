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
          <p className="text-lg">馬を選択してください</p>
          <p className="text-sm mt-1">ランキング表の馬名をクリック</p>
        </div>
      </div>
    );
  }

  const factorEntries = Object.entries(prediction.factor_scores);
  const labels = factorEntries.map(([, fs]) => fs.label);
  const scores = factorEntries.map(([, fs]) => fs.score);

  const data = {
    labels,
    datasets: [
      {
        label: prediction.horse_name,
        data: scores,
        backgroundColor: 'rgba(99, 102, 241, 0.2)',
        borderColor: 'rgba(99, 102, 241, 1)',
        borderWidth: 2,
        pointBackgroundColor: 'rgba(99, 102, 241, 1)',
        pointBorderColor: '#fff',
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
          stepSize: 20,
          color: 'rgba(156, 163, 175, 0.8)',
          backdropColor: 'transparent',
          font: { size: 10 },
        },
        grid: {
          color: 'rgba(156, 163, 175, 0.2)',
        },
        pointLabels: {
          color: 'rgba(209, 213, 219, 0.9)',
          font: { size: 11 },
        },
        angleLines: {
          color: 'rgba(156, 163, 175, 0.2)',
        },
      },
    },
    plugins: {
      legend: {
        labels: {
          color: 'rgba(209, 213, 219, 0.9)',
        },
      },
      tooltip: {
        callbacks: {
          label: (context: { dataset: { label?: string }; parsed: { r: number } }) => {
            return `${context.dataset.label ?? ''}: ${context.parsed.r.toFixed(1)}`;
          },
        },
      },
    },
  };

  return (
    <div className="card bg-base-100 shadow p-4">
      <h3 className="text-center font-semibold mb-2 text-sm opacity-80">{prediction.horse_name}</h3>
      <Radar data={data} options={options} />
    </div>
  );
}
