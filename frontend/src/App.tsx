import { BrowserRouter, Routes, Route, Link, useNavigate } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import RaceDetail from './pages/RaceDetail';
import HorseDetail from './pages/HorseDetail';
import NotFound from './pages/NotFound';

const APP_VERSION = '0.1.0';

function Header() {
  const navigate = useNavigate();

  return (
    <header className="navbar bg-base-100 shadow-lg sticky top-0 z-50">
      <div className="flex-1">
        <button
          className="btn btn-ghost text-xl gap-2"
          onClick={() => navigate('/')}
        >
          <span>🏇</span>
          <span className="hidden sm:inline">競馬予想システム</span>
          <span className="sm:hidden">競馬予想</span>
        </button>
      </div>
      <div className="flex-none">
        <ul className="menu menu-horizontal px-1 gap-1">
          <li>
            <Link to="/" className="btn btn-ghost btn-sm">
              ホーム
            </Link>
          </li>
        </ul>
      </div>
    </header>
  );
}

function Footer() {
  return (
    <footer className="footer footer-center bg-base-100 border-t border-base-200 p-6 mt-12">
      <div className="text-center space-y-1">
        <p className="text-sm opacity-60">
          🏇 競馬予想システム <span className="badge badge-sm badge-outline ml-1">v{APP_VERSION}</span>
        </p>
        <p className="text-xs opacity-40">
          © {new Date().getFullYear()} keiba-predictor. All rights reserved.
        </p>
      </div>
    </footer>
  );
}

function AppLayout() {
  return (
    <div className="min-h-screen bg-base-200 flex flex-col">
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
