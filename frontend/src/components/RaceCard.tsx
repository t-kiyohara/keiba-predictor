import { Link } from 'react-router-dom';
import { Race } from '../types';
import WeatherBadge from './WeatherBadge';

interface Props {
  race: Race;
}

const GRADE_CLASS: Record<string, string> = {
  G1: 'badge-error',
  G2: 'badge-warning',
  G3: 'badge-success',
};

export default function RaceCard({ race }: Props) {
  return (
    <div className="card bg-base-100 shadow hover:shadow-lg transition-shadow">
      <div className="card-body">
        <div className="flex items-start justify-between gap-2">
          <h2 className="card-title text-lg">{race.name}</h2>
          {race.grade && (
            <span className={`badge ${GRADE_CLASS[race.grade] ?? 'badge-neutral'} shrink-0`}>
              {race.grade}
            </span>
          )}
        </div>

        <div className="grid grid-cols-2 gap-x-4 gap-y-1 mt-2 text-sm">
          <div className="flex items-center gap-1 opacity-80">
            <span className="opacity-60">日付:</span>
            <span>{race.date}</span>
          </div>
          <div className="flex items-center gap-1 opacity-80">
            <span className="opacity-60">競馬場:</span>
            <span>{race.venue}</span>
          </div>
          <div className="flex items-center gap-1 opacity-80">
            <span className="opacity-60">コース:</span>
            <span>{race.course_type}</span>
          </div>
          <div className="flex items-center gap-1 opacity-80">
            <span className="opacity-60">距離:</span>
            <span>{race.distance}m</span>
          </div>
        </div>

        <div className="mt-2">
          <WeatherBadge weather={race.weather} trackCondition={race.track_condition} />
        </div>

        <div className="card-actions justify-end mt-2">
          <Link to={`/race/${race.id}`} className="btn btn-primary btn-sm">
            詳細を見る
          </Link>
        </div>
      </div>
    </div>
  );
}
