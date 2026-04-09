import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import RaceDetail from './pages/RaceDetail';
import HorseDetail from './pages/HorseDetail';

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-base-200">
        {/* ヘッダー */}
        <header className="navbar bg-base-100 shadow-lg">
          <div className="flex-1">
            <a href="/" className="btn btn-ghost text-xl">🏇 競馬予想システム</a>
          </div>
        </header>

        {/* メインコンテンツ */}
        <main className="container mx-auto px-4 py-8">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/race/:id" element={<RaceDetail />} />
            <Route path="/horse/:id" element={<HorseDetail />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
