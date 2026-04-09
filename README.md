# keiba-predictor

競馬重賞レースの予想システム。直近の重賞レースのデータを収集し、統計ベースのスコアリングで1〜3着を予想します。

## 技術スタック

- **Frontend**: React 18 + Vite + TypeScript + TailwindCSS + daisyUI
- **Backend**: Python 3.12 + FastAPI + SQLAlchemy + SQLite
- **Infrastructure**: Docker Compose

## セットアップ

### 前提条件
- Docker / Docker Compose

### 起動手順

1. リポジトリをクローン
2. 環境変数を設定
   ```bash
   cp .env.example .env
   # .env を編集して OPENWEATHER_API_KEY を設定
   ```
3. コンテナを起動
   ```bash
   make up
   ```
4. サンプルデータを投入
   ```bash
   make seed
   ```
5. ブラウザで http://localhost:5173 にアクセス

### その他のコマンド

| コマンド | 説明 |
|---------|------|
| `make up` | コンテナ起動 |
| `make down` | コンテナ停止 |
| `make restart` | 再起動 |
| `make logs` | ログ表示 |
| `make test` | テスト実行 |
| `make lint` | リンター実行 |
| `make seed` | サンプルデータ投入 |
| `make clean` | コンテナ + ボリューム削除 |

## スコアリングファクター

| ファクター | 重み | 説明 |
|-----------|------|------|
| 近走成績 | 20% | 直近5走の着順・上がり3F |
| 同レース成績 | 15% | 同名レースでの過去実績 |
| コース適性 | 15% | 同競馬場・同距離での成績 |
| 血統適性 | 15% | 父・母父の距離/コース傾向 |
| 馬場状態適性 | 10% | 良/稍重/重/不良での成績 |
| 騎手成績 | 10% | コース別・重賞別勝率 |
| 調教師成績 | 10% | コース別・重賞別成績 |
| 総合実績 | 5% | 通算勝率・重賞好走率 |
