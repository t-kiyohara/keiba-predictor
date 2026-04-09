import { Prediction } from '../types';

interface Props {
  predictions: Prediction[];
  onHorseClick: (horseId: string) => void;
}

const ROW_HIGHLIGHT: Record<number, string> = {
  1: 'bg-yellow-500/20',
  2: 'bg-gray-400/20',
  3: 'bg-amber-700/20',
};

const RANK_BADGE: Record<number, string> = {
  1: 'badge-warning',
  2: 'badge-ghost',
  3: 'badge-accent',
};

export default function ScoreTable({ predictions, onHorseClick }: Props) {
  // ファクターのキー一覧を取得（全馬共通と想定）
  const factorKeys =
    predictions.length > 0 ? Object.keys(predictions[0].factor_scores) : [];

  return (
    <div className="overflow-x-auto">
      <table className="table table-sm w-full">
        <thead>
          <tr>
            <th className="w-12">順位</th>
            <th>馬名</th>
            <th className="text-right">総合</th>
            {factorKeys.map((key) => (
              <th key={key} className="text-right text-xs opacity-70">
                {predictions[0]?.factor_scores[key]?.label ?? key}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {predictions.map((pred) => (
            <tr
              key={pred.horse_id}
              className={`cursor-pointer hover ${ROW_HIGHLIGHT[pred.rank] ?? ''}`}
              onClick={() => onHorseClick(pred.horse_id)}
            >
              <td>
                <span className={`badge badge-sm ${RANK_BADGE[pred.rank] ?? 'badge-neutral'}`}>
                  {pred.rank}
                </span>
              </td>
              <td className="font-semibold">{pred.horse_name}</td>
              <td className="text-right font-bold">{pred.total_score.toFixed(1)}</td>
              {factorKeys.map((key) => (
                <td key={key} className="text-right text-xs opacity-80">
                  {pred.factor_scores[key]?.weighted.toFixed(1) ?? '-'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
