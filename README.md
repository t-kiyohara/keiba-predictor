# 重賞スコープ

JRA重賞の予想を8ファクターのルールベーススコアで生成し、毎週末自動更新・答え合わせまで公開する個人プロジェクトです。

**公開サイト**: https://t-kiyohara.github.io/keiba-predictor/

## 仕組み

GitHub Actions の cron で、週次サイクルを自動運転しています。

- **土曜朝 6:00 JST**: 出馬表・オッズを取得 → 8ファクターで予想を生成 → GitHub Pages を更新
- **月曜朝 6:00 JST**: 確定したレース結果・払戻を取得 → 前週予想の的中率・回収率を検証 → GitHub Pages を更新

データは `db/keiba.sqlite3`（SQLite）としてリポジトリ本体に蓄積し、GitHub Actions がコミットします。取得したレース・成績・過去の予想はすべて履歴として保持し、削除しません。

## アーキテクチャ

- **Backend**: Python 3.12 + FastAPI + SQLAlchemy + Alembic / SQLite
  - `app/scrapers/` — JRA・netkeiba からのスクレイピング
  - `app/scoring/` — 8ファクターのスコアリングエンジン
  - `app/services/` — 取得・答え合わせ・静的JSON書き出しのオーケストレーション
  - `app/cli.py` — GitHub Actions から叩くバッチCLI（fetch / verify / backfill / export）
- **Frontend**: React 18 + Vite + TypeScript + TailwindCSS。「競馬新聞エディトリアル」をコンセプトにしたデザイン（詳細は `DESIGN.md`）
- **デプロイ**: `frontend/dist` を GitHub Pages に配信。本番ビルドはDBを叩かず、`app.cli export` が書き出す静的JSONのみを読む

### スコアリングファクター

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

## ローカル開発

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
4. サンプルデータを投入（レース日付は実行日から見た直近の土曜日に自動で付け替わります）
   ```bash
   make seed
   ```
5. ブラウザで http://localhost:5173 にアクセス

### コマンド

| コマンド | 説明 |
|---------|------|
| `make up` | コンテナ起動 |
| `make down` | コンテナ停止 |
| `make restart` | 再起動 |
| `make logs` | ログ表示 |
| `make test` | バックエンドのテスト実行（`docker compose exec backend pytest`） |
| `make lint` | ruff によるリンター実行 |
| `make seed` | サンプルデータ投入 |
| `make clean` | コンテナ + ボリューム削除 |

本番と同じバッチ処理をローカルで実行する場合は CLI を直接叩きます。

```bash
docker compose exec backend python -m app.cli fetch                    # 週末の重賞データ取得＋予想生成
docker compose exec backend python -m app.cli verify --days 8          # 確定したレース結果・払戻の取得（答え合わせ）
docker compose exec backend python -m app.cli backfill --years 5       # 過去のJRA重賞結果を一括収集
docker compose exec backend python -m app.cli export --out ../frontend/public/data  # DBから静的JSONを書き出し
```

## 免責と出典

- 本サイトの予想は独自スコアによる参考情報であり、的中を保証するものではありません。投資助言ではありません。
- データ出典: [netkeiba.com](https://www.netkeiba.com/)・[JRA](https://www.jra.go.jp/)
- スクレイピングは個人利用目的で行い、2秒間隔のレートリミットを遵守しています。
- 取得したデータの再配布・商用利用はできません（`LICENSE` の注記を参照）。

## ライセンス

コードは MIT License です（`LICENSE` を参照）。リポジトリに含まれるレースデータ（`db/keiba.sqlite3` 等）はライセンスの対象外で、個人・教育目的の利用に限られます。
