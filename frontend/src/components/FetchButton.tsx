import { useEffect, useRef, useState } from 'react';
import { FetchProgress } from '../types';
import { isStaticMode } from '../api/staticRoutes';

const POLL_INTERVAL_MS = 2000;
/** ポーリングの終了保証: 連続失敗がこの回数に達したら諦める */
const MAX_CONSECUTIVE_FAILURES = 5;
/** ポーリングの終了保証: 経過時間の上限 */
const MAX_POLL_DURATION_MS = 30 * 60 * 1000;

const TIMEOUT_MESSAGE =
  'データ取得の完了を確認できませんでした。時間をおいて再実行してください';

interface Props {
  onComplete: () => void;
}

/** ローカル環境のデータ取得ボタン。公開ビルド(静的モード)では表示しない */
export default function FetchButton({ onComplete }: Props) {
  const [fetching, setFetching] = useState(false);
  const [progress, setProgress] = useState<FetchProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current !== null) clearTimeout(timerRef.current);
    };
  }, []);

  if (isStaticMode) return null;

  const stop = (message: string | null) => {
    if (timerRef.current !== null) clearTimeout(timerRef.current);
    timerRef.current = null;
    setFetching(false);
    setProgress(null);
    setError(message);
  };

  /**
   * 進捗をポーリングする。完了は status === 'completed' のみで判定する
   * (current >= total は途中のステップでも成立するため使わない)。
   */
  const poll = async (startedAt: number, consecutiveFailures: number) => {
    if (Date.now() - startedAt > MAX_POLL_DURATION_MS) {
      stop(TIMEOUT_MESSAGE);
      return;
    }

    let failures = consecutiveFailures;
    try {
      const response = await fetch('/api/fetch/progress');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const latest: FetchProgress = await response.json();
      setProgress(latest);

      if (latest.status === 'completed') {
        stop(null);
        onComplete();
        return;
      }
      if (latest.status === 'error') {
        stop(latest.message || 'データを取得できませんでした。時間をおいて再実行してください');
        return;
      }
      failures = 0;
    } catch {
      failures += 1;
      if (failures >= MAX_CONSECUTIVE_FAILURES) {
        stop(TIMEOUT_MESSAGE);
        return;
      }
    }

    timerRef.current = setTimeout(() => void poll(startedAt, failures), POLL_INTERVAL_MS);
  };

  const handleFetch = async () => {
    setFetching(true);
    setError(null);
    setProgress(null);

    try {
      const response = await fetch('/api/fetch', { method: 'POST' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      void poll(Date.now(), 0);
    } catch {
      stop('データを取得できませんでした。時間をおいて再実行してください');
    }
  };

  const progressPercent =
    progress && progress.total > 0
      ? Math.min(100, Math.round((progress.current / progress.total) * 100))
      : 0;

  const formatRemaining = (seconds: number | null): string => {
    if (seconds === null) return '';
    if (seconds < 60) return `残り約${Math.ceil(seconds)}秒`;
    return `残り約${Math.ceil(seconds / 60)}分`;
  };

  return (
    <div className="flex flex-col items-end gap-2">
      <button type="button" className="btn-paper" onClick={handleFetch} disabled={fetching}>
        {fetching ? '取得中' : 'データ取得を実行'}
      </button>

      {error && (
        <p role="alert" className="text-caption text-shu">
          {error}
        </p>
      )}

      {fetching && progress && (
        <div className="w-64 space-y-1" aria-live="polite">
          <div className="flex justify-between gap-2 text-caption text-ink-weak">
            <span>
              {progress.step}
              {progress.message ? `: ${progress.message}` : ''}
            </span>
            <span className="shrink-0 tabular-nums">
              {formatRemaining(progress.estimated_remaining)}
            </span>
          </div>
          <div className="h-1 w-full bg-rule">
            <div className="h-1 bg-ink" style={{ width: `${progressPercent}%` }} />
          </div>
          <p className="text-right text-caption tabular-nums text-ink-weak">
            {progress.current} / {progress.total}
          </p>
        </div>
      )}
    </div>
  );
}
