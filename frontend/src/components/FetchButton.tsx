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

        // 完了判定: status で判定 + フォールバック
        if (data.status === 'completed' || (data.total > 0 && data.current >= data.total)) {
          stopPolling();
          setFetching(false);
          setProgress(null);
          onComplete();
        } else if (data.status === 'error') {
          stopPolling();
          setFetching(false);
          setError(data.message || 'データ取得中にエラーが発生しました');
          setProgress(null);
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
        className="btn-primary"
        onClick={handleFetch}
        disabled={fetching}
      >
        {fetching ? (
          <>
            <svg className="animate-spin h-4 w-4 mr-2" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            取得中...
          </>
        ) : (
          'データ取得'
        )}
      </button>

      {/* エラー表示 */}
      {error && (
        <div className="alert-error py-2 text-sm">
          <span>{error}</span>
        </div>
      )}

      {/* 進捗表示 */}
      {fetching && progress && (
        <div className="w-72 space-y-1">
          <div className="flex justify-between text-sm text-text-grey">
            <span>{progress.step}: {progress.message}</span>
            {progress.estimated_remaining !== null && (
              <span>{formatRemaining(progress.estimated_remaining)}</span>
            )}
          </div>
          <div className="w-full bg-stone-02 rounded-full h-2">
            <div
              className="h-2 rounded-full bg-primary transition-all duration-500"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <p className="text-xs text-text-disabled text-right">
            {progress.current} / {progress.total}
          </p>
        </div>
      )}
    </div>
  );
}
