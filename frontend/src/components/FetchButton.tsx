import { useState, useEffect, useRef } from 'react';
import { FetchProgress } from '../types';

interface Props {
  onComplete: () => void;
}

export default function FetchButton({ onComplete }: Props) {
  const [fetching, setFetching] = useState(false);
  const [progress, setProgress] = useState<FetchProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = () => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  };

  useEffect(() => {
    return () => stopPolling();
  }, []);

  const startPolling = () => {
    intervalRef.current = setInterval(async () => {
      try {
        const res = await fetch('/api/fetch/progress');
        if (!res.ok) return;
        const data: FetchProgress = await res.json();
        setProgress(data);

        // 完了判定: current === total かつ total > 0
        if (data.total > 0 && data.current >= data.total) {
          stopPolling();
          setFetching(false);
          setProgress(null);
          onComplete();
        }
      } catch {
        // ポーリング中のエラーは無視（一時的な接続エラーの可能性）
      }
    }, 2000);
  };

  const handleFetch = async () => {
    setFetching(true);
    setError(null);
    setProgress(null);

    try {
      const res = await fetch('/api/fetch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!res.ok) {
        throw new Error(`API Error: ${res.status} ${res.statusText}`);
      }

      // 取得開始後にポーリング開始
      startPolling();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setError(message);
      setFetching(false);
    }
  };

  const progressPercent =
    progress && progress.total > 0
      ? Math.round((progress.current / progress.total) * 100)
      : 0;

  const formatRemaining = (sec: number | null): string => {
    if (sec === null) return '';
    if (sec < 60) return `約${sec}秒`;
    return `約${Math.ceil(sec / 60)}分`;
  };

  return (
    <div className="flex flex-col gap-3 items-end">
      <button
        className="btn btn-primary"
        onClick={handleFetch}
        disabled={fetching}
      >
        {fetching ? (
          <>
            <span className="loading loading-spinner loading-sm"></span>
            取得中...
          </>
        ) : (
          'データ取得'
        )}
      </button>

      {/* エラー表示 */}
      {error && (
        <div className="alert alert-error py-2 text-sm">
          <span>{error}</span>
        </div>
      )}

      {/* 進捗表示 */}
      {fetching && progress && (
        <div className="w-72 space-y-1">
          <div className="flex justify-between text-sm opacity-80">
            <span>{progress.step}: {progress.message}</span>
            {progress.estimated_remaining !== null && (
              <span>{formatRemaining(progress.estimated_remaining)}</span>
            )}
          </div>
          <progress
            className="progress progress-primary w-full"
            value={progressPercent}
            max={100}
          ></progress>
          <p className="text-xs opacity-60 text-right">
            {progress.current} / {progress.total}
          </p>
        </div>
      )}
    </div>
  );
}
