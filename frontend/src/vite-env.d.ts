/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 'static' のとき /api ではなく ${BASE_URL}data/*.json を読む(公開ビルド) */
  readonly VITE_DATA_MODE?: 'static' | 'api';
}
