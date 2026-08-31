import {
  CategoryScale,
  Chart as ChartJS,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import { Stats as StatsData, StatsRow } from '../types';
import { useResource } from '../hooks/useApi';
import { formatPaperDate, gradeBadgeClass, paperColor } from '../constants/paper';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip);

const EMPTY_MESSAGE = '検証済みレースがまだありません。毎週月曜朝に更新されます';

/** 回収率・収支の符号色。プラス=朱 / マイナス=藍(DESIGN.md §2) */
function signColor(value: number, breakEven = 0): string {
  return value >= breakEven ? 'text-shu' : 'text-ai';
}

function Figure({
  label,
  value,
  valueClass,
  note,
}: {
  label: string;
  value: string;
  valueClass?: string;
  note?: string;
}) {
  return (
    <div>
      <p className="text-caption text-ink-weak">{label}</p>
      <p className={`text-figure font-bold tabular-nums ${valueClass ?? 'text-ink'}`}>{value}</p>
      {note && <p className="text-caption text-ink-weak">{note}</p>}
    </div>
  );
}

/** 累計収支の折れ線(墨の細線・塗りなし・収支0の基準線を罫色破線で / DESIGN.md §5-3) */
function BalanceChart({ points }: { points: StatsData['cumulative'] }) {
  const ink = paperColor('ink');
  const shu = paperColor('shu');
  const rule = paperColor('rule');
  const inkWeak = paperColor('ink-weak');

  const balances = points.map((point) => point.balance_win + point.balance_place);

  return (
    <div className="h-60">
      <Line
        data={{
          labels: points.map((point) => formatPaperDate(point.date)),
          datasets: [
            {
              label: '累計収支',
              data: balances,
              borderColor: ink,
              borderWidth: 1,
              pointRadius: 0,
              pointHitRadius: 8,
              tension: 0,
              fill: false,
              // プラス圏の区間だけ朱にする
              segment: {
                borderColor: (context) =>
                  (context.p0.parsed.y ?? 0) >= 0 && (context.p1.parsed.y ?? 0) >= 0
                    ? shu
                    : ink,
              },
            },
            {
              label: '収支0(回収率100%)',
              data: points.map(() => 0),
              borderColor: rule,
              borderWidth: 1,
              borderDash: [4, 4],
              pointRadius: 0,
              tension: 0,
              fill: false,
            },
          ],
        }}
        options={{
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: 'index', intersect: false },
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: ink,
              displayColors: false,
              callbacks: {
                label: (context) =>
                  context.datasetIndex === 0
                    ? `累計収支 ${(context.parsed.y ?? 0).toLocaleString('ja-JP')}円`
                    : '',
              },
            },
          },
          scales: {
            x: {
              grid: { display: false },
              border: { color: rule },
              ticks: {
                color: inkWeak,
                font: { family: '"IBM Plex Sans JP", sans-serif', size: 11 },
                maxRotation: 0,
                autoSkip: true,
                maxTicksLimit: 6,
              },
            },
            y: {
              grid: { display: false },
              border: { color: rule },
              ticks: {
                color: inkWeak,
                font: { family: '"IBM Plex Sans JP", sans-serif', size: 11 },
                maxTicksLimit: 5,
                callback: (value) => `${Number(value).toLocaleString('ja-JP')}`,
              },
            },
          },
        }}
      />
    </div>
  );
}

function PayoutCell({ payout }: { payout: number }) {
  if (payout <= 0) {
    return <td className="px-2 py-1.5 text-right text-ink-weak">―</td>;
  }
  return (
    <td className="px-2 py-1.5 text-right font-bold tabular-nums text-shu">
      {payout.toLocaleString('ja-JP')}
    </td>
  );
}

/** 回顧表(1行=1レース / DESIGN.md §5-3) */
function ReviewTable({ rows }: { rows: StatsRow[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-data">
        <caption className="sr-only">レースごとの回顧</caption>
        <thead>
          <tr className="bg-paper-inset text-left text-caption text-ink-weak">
            <th scope="col" className="whitespace-nowrap px-2 py-1 font-medium">
              日付
            </th>
            <th scope="col" className="px-2 py-1 font-medium">
              レース
            </th>
            <th scope="col" className="px-2 py-1 font-medium">
              ◎馬名
            </th>
            <th scope="col" className="px-2 py-1 text-right font-medium">
              結果
            </th>
            <th scope="col" className="px-2 py-1 text-right font-medium">
              単勝払戻
            </th>
            <th scope="col" className="px-2 py-1 text-right font-medium">
              複勝払戻
            </th>
            <th scope="col" className="px-2 py-1 text-right font-medium">
              収支
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={`${row.date}-${row.race_id}`}
              className="border-t border-rule transition-colors hover:bg-paper-inset"
            >
              <td className="whitespace-nowrap px-2 py-1.5 tabular-nums text-ink-weak">
                {formatPaperDate(row.date)}
              </td>
              <td className="px-2 py-1.5">
                <span className="font-mincho font-bold text-ink">{row.race_name}</span>
                {row.grade && (
                  <span className={`ml-1.5 ${gradeBadgeClass(row.grade)}`}>{row.grade}</span>
                )}
                <span className="ml-1.5 text-caption text-ink-weak">{row.venue}</span>
              </td>
              <td className="px-2 py-1.5">
                <span className="mark mr-1 text-shu" role="img" aria-label="本命">
                  ◎
                </span>
                <span className="text-ink">{row.pick_horse_name}</span>
                {row.pick_odds !== null && (
                  <span className="ml-1 text-caption tabular-nums text-ink-weak">
                    {row.pick_odds.toFixed(1)}倍
                  </span>
                )}
              </td>
              <td className="px-2 py-1.5 text-right tabular-nums text-ink">
                {row.finish_position !== null ? `${row.finish_position}着` : '―'}
              </td>
              <PayoutCell payout={row.win_payout} />
              <PayoutCell payout={row.place_payout} />
              <td
                className={`px-2 py-1.5 text-right font-bold tabular-nums ${signColor(row.net)}`}
              >
                {row.net > 0 ? '+' : ''}
                {row.net.toLocaleString('ja-JP')}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Stats() {
  // /api/stats 未実装(404)のあいだは空状態にフォールバックする
  const { value, status } = useResource<StatsData>('/stats');
  const summary = value?.summary ?? null;
  const rows = value?.rows ?? [];
  const cumulative = value?.cumulative ?? [];
  const isEmpty = summary === null || summary.races === 0;
  const periodStart = rows.length > 0 ? rows[0].date : null;

  return (
    <div>
      <div className="rule-heavy flex flex-wrap items-baseline justify-between gap-2 pb-2">
        <h1 className="font-mincho text-race-name font-bold text-ink">的中実績</h1>
        {periodStart && (
          <p className="text-data tabular-nums text-ink-weak">
            集計期間 {periodStart.replace(/-/g, '/')}〜
          </p>
        )}
      </div>

      {status === 'loading' && (
        <p className="py-6 text-center text-data text-ink-weak">的中実績を読み込んでいます</p>
      )}

      {status !== 'loading' && isEmpty && (
        <p className="py-8 text-center text-data text-ink-weak">{EMPTY_MESSAGE}</p>
      )}

      {status !== 'loading' && !isEmpty && summary && (
        <>
          <section className="rule-b grid grid-cols-2 gap-4 py-4 md:grid-cols-4">
            <Figure
              label="単勝回収率"
              value={`${(summary.win_roi * 100).toFixed(1)}%`}
              valueClass={signColor(summary.win_roi, 1)}
              note={`的中率 ${(summary.win_hit_rate * 100).toFixed(1)}%`}
            />
            <Figure
              label="複勝回収率"
              value={`${(summary.place_roi * 100).toFixed(1)}%`}
              valueClass={signColor(summary.place_roi, 1)}
            />
            <Figure
              label="◎複勝率"
              value={`${(summary.place_hit_rate * 100).toFixed(1)}%`}
              note={`上位3頭の3着内率 ${(summary.top3_in_top_picks * 100).toFixed(1)}%`}
            />
            <Figure
              label="対象"
              value={`${summary.races}R`}
              valueClass="text-ink-weak"
              note="単勝100円+複勝100円/レース"
            />
          </section>

          {cumulative.length > 0 && (
            <section className="rule-b py-4">
              <h2 className="mb-2 font-mincho text-heading font-bold text-ink">累計収支</h2>
              <BalanceChart points={cumulative} />
            </section>
          )}

          {rows.length > 0 && (
            <section className="py-4">
              <h2 className="mb-2 font-mincho text-heading font-bold text-ink">回顧</h2>
              <ReviewTable rows={rows} />
            </section>
          )}
        </>
      )}
    </div>
  );
}
