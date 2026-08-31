/* 公開ビルド(GitHub Pages)用の /api → 静的 JSON マッピング。
   data-contract.md v1 が定義するファイル構成を、既存の /api パスに読み替える。
   マッピングの知識はこのモジュールだけが持つ(呼び出し側は /api パスのまま書く)。 */

export const isStaticMode = import.meta.env.VITE_DATA_MODE === 'static';

export interface StaticRoute {
  url: string;
  /** races/{id}.json のように1ファイルが複数エンドポイントを充足する場合の取り出し */
  extract?: (payload: unknown) => unknown;
}

const dataUrl = (name: string): string => `${import.meta.env.BASE_URL}data/${name}`;

const pick =
  (key: string) =>
  (payload: unknown): unknown =>
    (payload as Record<string, unknown> | null)?.[key] ?? null;

/** 対応する静的ファイルがなければ null(例: /fetch は公開ビルドに存在しない) */
export function resolveStaticRoute(path: string): StaticRoute | null {
  if (path === '/races') return { url: dataUrl('races.json') };
  if (path === '/stats') return { url: dataUrl('stats.json') };
  if (path === '/meta') return { url: dataUrl('meta.json') };

  const raceMatch = path.match(/^\/races\/([^/]+)(\/predictions|\/entries)?$/);
  if (raceMatch) {
    const [, raceId, subPath] = raceMatch;
    const url = dataUrl(`races/${encodeURIComponent(raceId)}.json`);
    if (subPath === '/predictions') return { url, extract: pick('predictions') };
    if (subPath === '/entries') return { url, extract: pick('entries') };
    return { url, extract: pick('race') };
  }

  const horseMatch = path.match(/^\/horses\/([^/]+)(\/results)?$/);
  if (horseMatch) {
    const [, horseId, subPath] = horseMatch;
    const url = dataUrl(`horses/${encodeURIComponent(horseId)}.json`);
    return { url, extract: pick(subPath === '/results' ? 'results' : 'horse') };
  }

  return null;
}
