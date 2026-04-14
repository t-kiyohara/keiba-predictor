import { BrowserRouter, Routes, Route, Link, useNavigate } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import RaceDetail from './pages/RaceDetail';
import HorseDetail from './pages/HorseDetail';
import NotFound from './pages/NotFound';

const APP_VERSION = '0.1.0';

function Header() {
  const navigate = useNavigate();

  return (
    <header className="bg-surface shadow-sm border-b border-border sticky top-0 z-50">
      <div className="container mx-auto px-4 flex items-center justify-between">
        <button
          className="btn-ghost text-xl gap-2"
          onClick={() => navigate('/')}
        >
          <span>🏇</span>
          <span className="hidden desktop:inline">競馬予想システム</span>
          <span className="desktop:hidden">競馬予想</span>
        </button>
        <nav className="flex items-center gap-1">
          <Link to="/" className="btn-ghost btn-sm text-sm">
            ホーム
          </Link>
        </nav>
      </div>
    </header>
  );
}

function Footer() {
  return (
    <footer className="bg-surface border-t border-border p-6 mt-12 text-center">
      <div className="space-y-1">
        <p className="text-sm text-text-grey">
          🏇 競馬予想システム{' '}
          <span className="badge-smarthr border border-border text-text-grey ml-1">
            v{APP_VERSION}
          </span>
        </p>
        <p className="text-xs text-text-disabled">
          © {new Date().getFullYear()} keiba-predictor. All rights reserved.
        </p>
      </div>
    </footer>
  );
}

function AppLayout() {
  return (
    <div className="min-h-screen bg-stone-01 flex flex-col">
      <Header />

      {/* メインコンテンツ */}
      <main className="container mx-auto px-4 py-8 flex-1">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/race/:id" element={<RaceDetail />} />
          <Route path="/horse/:id" element={<HorseDetail />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>

      <Footer />
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppLayout />
    </BrowserRouter>
  );
}

export default App;
