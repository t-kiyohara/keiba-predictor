import React from 'react';
import ReactDOM from 'react-dom/client';

/* フォントは @fontsource でセルフホスト(Pages 配信のため CDN 依存を避ける / DESIGN.md §3)。
   japanese サブセットは和文、latin サブセットは数字・英字(tabular-nums 用)に必要。 */
import '@fontsource/shippori-mincho-b1/japanese-700.css';
import '@fontsource/shippori-mincho-b1/japanese-800.css';
import '@fontsource/shippori-mincho-b1/latin-700.css';
import '@fontsource/shippori-mincho-b1/latin-800.css';
import '@fontsource/ibm-plex-sans-jp/japanese-400.css';
import '@fontsource/ibm-plex-sans-jp/japanese-500.css';
import '@fontsource/ibm-plex-sans-jp/japanese-700.css';
import '@fontsource/ibm-plex-sans-jp/latin-400.css';
import '@fontsource/ibm-plex-sans-jp/latin-500.css';
import '@fontsource/ibm-plex-sans-jp/latin-700.css';

import App from './App.tsx';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
