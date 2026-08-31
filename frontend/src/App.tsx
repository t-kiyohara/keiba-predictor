import { BrowserRouter, NavLink, Route, Routes } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import RaceDetail from './pages/RaceDetail';
import HorseDetail from './pages/HorseDetail';
import Stats from './pages/Stats';
import NotFound from './pages/NotFound';
import { useResource } from './hooks/useApi';
import { formatTimestamp } from './constants/paper';
import { DataMeta } from './types';

const NAV_ITEMS = [
  { to: '/', label: '番組表' },
  { to: '/stats', label: '的中実績' },
];

function navLinkClass({ isActive }: { isActive: boolean }): string {
  return [
    'px-2 py-1 text-data transition-colors hover:bg-paper-inset',
    isActive ? 'font-bold text-shu' : 'text-ink',
  ].join(' ');
}

/** 題字ヘッダー(DESIGN.md §5 共通シェル) */
function Masthead({ updatedAt }: { updatedAt: string | null }) {
  return (
    <header className="rule-b">
      <div className="mx-auto flex max-w-page flex-wrap items-end justify-between gap-2 px-4 py-3">
        <NavLink to="/" className="font-mincho text-logo font-extrabold text-ink">
          重賞スコープ
        </NavLink>
        <div className="flex flex-col items-end gap-1">
          <nav aria-label="サイト内ナビゲーション" className="flex items-center gap-1">
            {NAV_ITEMS.map((item, index) => (
              <span key={item.to} className="flex items-center gap-1">
                {index > 0 && (
                  <span aria-hidden="true" className="text-rule">
                    /
                  </span>
                )}
                <NavLink to={item.to} end={item.to === '/'} className={navLinkClass}>
                  {item.label}
                </NavLink>
              </span>
            ))}
          </nav>
          {updatedAt && (
            <p className="text-caption text-ink-weak">データ更新 {updatedAt}</p>
          )}
        </div>
      </div>
    </header>
  );
}

/** 免責と出典(DESIGN.md §8 の文言をそのまま) */
function Colophon({ updatedAt }: { updatedAt: string | null }) {
  return (
    <footer className="rule-t mt-10">
      <div className="mx-auto max-w-page px-4 py-4">
        <p className="text-caption text-ink-weak">
          本サイトの予想は独自スコアによる参考情報であり、的中を保証するものではありません。投資助言ではありません。
          {' / '}
          データ出典: netkeiba.com・JRA
          {' / '}
          最終更新: {updatedAt ?? '不明'}
        </p>
      </div>
    </footer>
  );
}

function PaperLayout() {
  const meta = useResource<DataMeta>('/meta');
  const updatedAt = meta.value?.generated_at
    ? formatTimestamp(meta.value.generated_at)
    : null;

  return (
    <div className="flex min-h-screen flex-col bg-paper">
      <Masthead updatedAt={updatedAt} />
      <main className="mx-auto w-full max-w-page flex-1 px-4 py-5">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/race/:id" element={<RaceDetail />} />
          <Route path="/horse/:id" element={<HorseDetail />} />
          <Route path="/stats" element={<Stats />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <Colophon updatedAt={updatedAt} />
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter basename={import.meta.env.BASE_URL}>
      <PaperLayout />
    </BrowserRouter>
  );
}
