import { TRACK_CONDITION_CLASS } from '../constants/badge';

interface Props {
  weather: string | null;
  trackCondition: string | null;
}

const WEATHER_ICON: Record<string, string> = {
  晴れ: '☀️',
  晴: '☀️',
  曇り: '☁️',
  曇: '☁️',
  雨: '🌧️',
  雪: '❄️',
};

export default function WeatherBadge({ weather, trackCondition }: Props) {
  const weatherIcon = weather ? (WEATHER_ICON[weather] ?? '🌤️') : null;

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {/* 天気バッジ */}
      <span className="badge-smarthr border border-border text-text-grey gap-1">
        {weatherIcon && <span>{weatherIcon}</span>}
        <span>{weather ?? '未定'}</span>
      </span>

      {/* 馬場状態バッジ */}
      <span className={TRACK_CONDITION_CLASS[trackCondition ?? ''] ?? 'badge-smarthr bg-stone-02 text-stone-04'}>
        {trackCondition ?? '未定'}
      </span>
    </div>
  );
}
