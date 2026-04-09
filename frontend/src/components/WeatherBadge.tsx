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

const TRACK_CONDITION_CLASS: Record<string, string> = {
  良: 'badge-success',
  稍重: 'badge-warning',
  重: 'badge-error',
  不良: 'badge-error',
};

export default function WeatherBadge({ weather, trackCondition }: Props) {
  const weatherIcon = weather ? (WEATHER_ICON[weather] ?? '🌤️') : null;

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {/* 天気バッジ */}
      <span className="badge badge-outline gap-1">
        {weatherIcon && <span>{weatherIcon}</span>}
        <span>{weather ?? '未定'}</span>
      </span>

      {/* 馬場状態バッジ */}
      <span className={`badge ${TRACK_CONDITION_CLASS[trackCondition ?? ''] ?? 'badge-neutral'}`}>
        {trackCondition ?? '未定'}
      </span>
    </div>
  );
}
