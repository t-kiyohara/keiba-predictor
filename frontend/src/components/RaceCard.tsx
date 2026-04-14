import { Link } from 'react-router-dom';
import { Race } from '../types';
import WeatherBadge from './WeatherBadge';
import { GRADE_CLASS } from '../constants/badge';

interface Props {
  race: Race;
}

export default function RaceCard({ race }: Props) {
  return (
    <div className="card-smarthr hover:shadow-md transition-shadow">
      <div className="p-4">
        <div className="flex items-start justify-between gap-2">
          <h2 className="text-lg font-bold text-text-black">{race.name}</h2>
          {race.grade && (
            <span className={`${GRADE_CLASS[race.grade] ?? 'badge-smarthr bg-stone-02 text-stone-04'} shrink-0`}>
              {race.grade}
            </span>
          )}
        </div>

        <div className="grid grid-cols-2 gap-x-4 gap-y-1 mt-2 text-sm">
          <div className="flex items-center gap-1 text-text-grey">
            <span className="text-text-disabled">日付:</span>
            <span>{race.date}</span>
          </div>
          <div className="flex items-center gap-1 text-text-grey">
            <span className="text-text-disabled">競馬場:</span>
            <span>{race.venue}</span>
          </div>
          <div className="flex items-center gap-1 text-text-grey">
            <span className="text-text-disabled">コース:</span>
            <span>{race.course_type}</span>
          </div>
          <div className="flex items-center gap-1 text-text-grey">
            <span className="text-text-disabled">距離:</span>
            <span>{race.distance}m</span>
          </div>
        </div>

        <div className="mt-2">
          <WeatherBadge weather={race.weather} trackCondition={race.track_condition} />
        </div>

        <div className="flex justify-end mt-2">
          <Link to={`/race/${race.id}`} className="btn-primary btn-sm">
            詳細を見る
          </Link>
        </div>
      </div>
    </div>
  );
}
