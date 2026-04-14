import { Prediction } from '../types';
import { RANK_BADGE } from '../constants/badge';

interface Props {
  predictions: Prediction[];
  onHorseClick: (horseId: string) => void;
  selectedHorseId?: string | null;
}

const ROW_HIGHLIGHT: Record<number, string> = {
  1: 'bg-yellow-500/20',
  2: 'bg-gray-400/20',
  3: 'bg-amber-700/20',
};

export default function ScoreTable({ predictions, onHorseClick, selectedHorseId }: Props) {
  const factorKeys =
    predictions.length > 0 ? Object.keys(predictions[0].factor_scores) : [];

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-stone-02">
            <th className="px-3 py-2 text-left text-xs font-semibold text-text-grey w-12">順位</th>
            <th className="px-3 py-2 text-left text-xs font-semibold text-text-grey w-10">馬番*</th>
            <th className="px-3 py-2 text-left text-xs font-semibold text-text-grey">馬名</th>
            <th className="px-3 py-2 text-right text-xs font-semibold text-text-grey">総合</th>
            {factorKeys.map((key) => (
              <th key={key} className="px-3 py-2 text-right text-xs font-semibold text-text-grey">
                {predictions[0]?.factor_scores[key]?.label ?? key}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {predictions.map((pred) => {
            const isSelected = selectedHorseId === pred.horse_id;
            return (
              <tr
                key={pred.horse_id}
                className={[
                  'cursor-pointer transition-all duration-150 border-t border-border',
                  isSelected
                    ? 'bg-primary/10 ring-1 ring-inset ring-primary/50'
                    : `hover:bg-over-bg ${ROW_HIGHLIGHT[pred.rank] ?? ''}`,
                ].join(' ')}
                onClick={() => onHorseClick(pred.horse_id)}
              >
                <td className="px-3 py-2">
                  <span className={RANK_BADGE[pred.rank] ?? 'badge-smarthr bg-stone-02 text-stone-04'}>
                    {pred.rank}
                  </span>
                </td>
                <td className="px-3 py-2 text-xs text-text-disabled font-mono">{pred.rank}</td>
                <td className={`px-3 py-2 font-semibold ${isSelected ? 'text-primary' : 'text-text-black'}`}>
                  {pred.horse_name}
                </td>
                <td className="px-3 py-2 text-right font-bold text-text-black">
                  {pred.total_score.toFixed(1)}
                </td>
                {factorKeys.map((key) => (
                  <td key={key} className="px-3 py-2 text-right text-xs text-text-grey">
                    {pred.factor_scores[key]?.weighted.toFixed(1) ?? '-'}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
