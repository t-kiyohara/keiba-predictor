import { useCallback, useEffect, useState } from 'react';
import { isStaticMode, resolveStaticRoute } from '../api/staticRoutes';

/** ユーザーに出すエラー文面(DESIGN.md §8: 原因と次の行動) */
export const FETCH_ERROR_MESSAGE =
  'データを取得できませんでした。時間をおいて再実行してください';

/**
 * 単発 GET。パスは常に /api を除いた形(例: '/races/123/predictions')で渡す。
 * 静的モードでは staticRoutes のマッピングを通して JSON ファイルを読む。
 * 失敗時は throw する。
 */
export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const staticRoute = isStaticMode ? resolveStaticRoute(path) : null;
  if (isStaticMode && staticRoute === null) {
    throw new Error(`公開ビルドでは利用できません: ${path}`);
  }

  const url = staticRoute ? staticRoute.url : `/api${path}`;
  const response = await fetch(url, { signal });
  if (!response.ok) {
    throw new Error(`${FETCH_ERROR_MESSAGE} (${response.status})`);
  }

  // 静的ファイルが無い場合、dev サーバは SPA フォールバックの HTML を 200 で返す
  const payload: unknown = await response.json().catch(() => {
    throw new Error(FETCH_ERROR_MESSAGE);
  });

  return (staticRoute?.extract ? staticRoute.extract(payload) : payload) as T;
}

export type ResourceStatus = 'loading' | 'ready' | 'error';

export interface Resource<T> {
  value: T | null;
  status: ResourceStatus;
  reload: () => void;
}

/**
 * 欄(セクション)単位でデータを読む。1ページに複数の欄がある画面で、
 * 片方の loading / error が全画面を潰さないようにするための単位。
 * path に null を渡すと何も読まない。
 */
export function useResource<T>(path: string | null): Resource<T> {
  const [value, setValue] = useState<T | null>(null);
  const [status, setStatus] = useState<ResourceStatus>(path ? 'loading' : 'ready');
  const [reloadCount, setReloadCount] = useState(0);

  useEffect(() => {
    if (!path) {
      setValue(null);
      setStatus('ready');
      return;
    }

    const controller = new AbortController();
    setStatus('loading');
    apiGet<T>(path, controller.signal)
      .then((loaded) => {
        setValue(loaded);
        setStatus('ready');
      })
      .catch((err: unknown) => {
        if (err instanceof Error && err.name === 'AbortError') return;
        setValue(null);
        setStatus('error');
      });

    return () => controller.abort();
  }, [path, reloadCount]);

  const reload = useCallback(() => setReloadCount((count) => count + 1), []);

  return { value, status, reload };
}
