# リファクタリング設計書

## Context

keiba-predictor は JRA/netkeiba からレースデータをスクレイピングし、8つの重み付き要因でスコアリングして予測を表示する競馬予測システムである。MVP として動作しているが、急速な機能追加により以下の技術的負債が蓄積している:

- **重複コード**: 勝率計算が4箇所、jockey/trainer スコアリングがほぼ同一、グレード正規化マップが2ファイル、テストヘルパーが3ファイルで重複
- **巨大メソッド**: `fetch_race_entries()` 195行、`FetchService.execute()` 197行、`fetch_horse_results()` 132行
- **パフォーマンス問題**: スコアリングで1レースあたり144+のN+1クエリ、DBインデックスなし
- **型安全性不足**: バックエンドにPydanticスキーマなし、フロントエンドで `string` 型を使うべきところにユニオン型未使用
- **テスト不足**: `FetchService.execute()`、実データスコアリング、`WeatherClient` API応答のテストが欠落

本リファクタリングは、機能追加ではなくコード品質の全面的な底上げを目的とする。

## アプローチ

**ボトムアップ型の5段階リファクタリング。** 小さな変更から積み上げ、各段階の完了時にOpus 4.6サブエージェントによるコードレビューを必ず実施する。

## レビュー方針

- 各段階の完了時に `superpowers:code-reviewer` サブエージェント (model: opus) でレビュー
- 実装は sonnet で実行
- 各段階で `make test` + `make lint` の回帰テスト確認

---

## 段階1: 共通化・定数整理

**目的:** 重複コードの排除とマジックナンバーの定数化。後続段階の基盤。

### 1-1. 勝率計算ヘルパー抽出

**対象:** `backend/app/scoring/factors.py`

4箇所で重複している勝率→加重スコア計算を共通関数に抽出:
- L165-175 (`score_course_aptitude` 内の `calc_score`)
- L224-233 (`score_track_condition` 内のインライン計算)
- L247-257 (`score_jockey` 内の `calc_win_rate_score`)
- L306-316 (`score_trainer` 内の `calc_win_rate_score`)

```python
def _win_rate_score(
    results: list[Result],
    w_win: float = 60,
    w_rentai: float = 30,
    w_fukusho: float = 10,
) -> float:
    """勝率・連対率・複勝率から加重スコアを算出"""
    if not results:
        return NEUTRAL_SCORE
    total = len(results)
    win_rate = sum(1 for r in results if r.finish_position == 1) / total
    rentai_rate = sum(1 for r in results if r.finish_position <= 2) / total
    fukusho_rate = sum(1 for r in results if r.finish_position <= 3) / total
    raw = win_rate * w_win + rentai_rate * w_rentai + fukusho_rate * w_fukusho
    return min(raw + 50, 100)
```

### 1-2. jockey/trainer スコアリング統合

**対象:** `backend/app/scoring/factors.py`

`score_jockey` (L237-295) と `score_trainer` (L297-352) はほぼ同一。差異は `Entry.jockey_id` vs `Entry.trainer_id` のみ。

```python
def _score_person(
    db: Session,
    person_id: str | None,
    person_id_attr,  # Entry.jockey_id or Entry.trainer_id
    race: Race,
    # ...
) -> float:
```

`score_jockey` と `score_trainer` はこの共通関数を呼ぶ薄いラッパーに。

### 1-3. グレード正規化マップ統合

**対象:** `backend/app/scrapers/netkeiba.py` (L23-33), `backend/app/scrapers/jra.py` (L36-43)

新規ファイル `backend/app/scrapers/constants.py` に統合:
- `GRADE_NORMALIZE: dict[str, str]`
- `GRADE_PATTERN: re.Pattern`

両スクレイパーからインポート。

### 1-4. スコアリング定数の名前付き定数化

**対象:** `backend/app/scoring/weights.py`

追加する定数:
- `NEUTRAL_SCORE = 50.0` — データなし時のデフォルトスコア (現在 factors.py 内に11箇所散在)
- `DISTANCE_TOLERANCE_M = 200` — 距離マッチングの許容範囲 (3箇所で使用)

### 1-5. フロントエンド定数統合

**新規:** `frontend/src/constants/badge.ts`

以下を統合:
- `TRACK_CONDITION_CLASS` — WeatherBadge.tsx (L15-20) と HorseDetail.tsx (L6-11) で重複
- `RANK_BADGE` — RaceDetail.tsx (L16-20) と ScoreTable.tsx (L15-19) で重複
- `GRADE_CLASS` — RaceCard.tsx (L9-13) を正とし、RaceDetail.tsx (L140) のインライン三項演算子を置き換え

### 1-6. CORS origin を Settings に移動

**対象:** `backend/app/config.py`, `backend/app/main.py` (L20)

`Settings` クラスに `CORS_ORIGINS: list[str]` を追加し、`main.py` のハードコードを置き換え。

### 検証

- `make test` 全テストパス
- `make lint` エラーなし
- 各スコアリング関数の出力が変更前と同一であることを確認

---

## 段階2: 巨大メソッド分割

**目的:** 長大なメソッドを読みやすく保守しやすい単位に分解する。

### 2-1. `NetkeibaScraper.fetch_race_entries()` 分割

**対象:** `backend/app/scrapers/netkeiba.py` (L107-302, 195行)

3メソッドに分割:
- `_parse_race_info(soup: BeautifulSoup) -> dict` — レース情報 (距離, コース種別, レース名, グレード, 会場, 日付) の抽出
- `_parse_entry_table(soup: BeautifulSoup, race_id: str) -> list[dict]` — 出走表テーブルのパース
- `fetch_race_entries(race_id)` — フェッチ + 上記2つを呼ぶオーケストレータ

### 2-2. `NetkeibaScraper.fetch_horse_results()` 分割

**対象:** `backend/app/scrapers/netkeiba.py` (L407-539, 132行)

2メソッドに分割:
- `_detect_column_indices(header_row) -> dict[str, int]` — ヘッダー行からカラムインデックスを検出
- `_parse_result_row(row, col_indices: dict) -> dict | None` — 各行のパース (Noneはスキップ行)

### 2-3. `NetkeibaScraper.fetch_horse_profile()` 分割

**対象:** `backend/app/scrapers/netkeiba.py` (L304-405, 101行)

2メソッドに分割:
- `_parse_profile_page(soup: BeautifulSoup) -> dict` — プロフィールページのパース
- `_fetch_pedigree(horse_id: str) -> dict` — 血統AJAX (euc-jp) のフェッチとパース

### 2-4. `JraScraper.fetch_graded_races()` 分割

**対象:** `backend/app/scrapers/jra.py` (L55-171, 116行)

2メソッドに分割:
- `_parse_race_card(race_block, race_date) -> dict | None` — 個別レースカードのパース
- `fetch_graded_races()` — ページフェッチ + `_parse_race_card` の反復呼び出し

### 2-5. `FetchService.execute()` 分割

**対象:** `backend/app/services/fetch_service.py` (L32-229, 197行)

7ステップメソッドに分割:
- `_step_determine_dates()` → target_dates
- `_step_fetch_race_list(target_dates)` → graded_races
- `_step_fetch_entries(graded_races)` → entries per race
- `_step_fetch_profiles(horse_ids)` → profiles
- `_step_fetch_results(horse_ids)` → results
- `_step_fetch_weather(races)` → weather data
- `_step_score(races)` → predictions

`execute()` はステップを順次呼ぶオーケストレータに。`TOTAL_STEPS = 7` を自動計算可能に。

### 2-6. `_venue_from_race_id()` の公開化

**対象:** `backend/app/scrapers/netkeiba.py`

`_venue_from_race_id` → `venue_from_race_id` にリネーム。`fetch_service.py` でのインポートを更新。

### 検証

- `make test` 全テストパス
- `make lint` エラーなし
- 各スクレイパーメソッドの動作が変更前と同一 (既存テストで検証)

---

## 段階3: アーキテクチャ改善

**目的:** APIの型安全性、DBパフォーマンス、関心の分離を改善。

### 3-1. Pydantic レスポンスモデル導入

**新規ディレクトリ:** `backend/app/schemas/`

- `race.py` — `RaceResponse`, `RaceListResponse`
- `horse.py` — `HorseResponse`, `HorseResultResponse`
- `prediction.py` — `PredictionResponse`
- `fetch.py` — `FetchProgressResponse`

ルーター (`races.py`, `horses.py`, `fetch.py`) の手動dict構築をPydanticモデルに置き換え。FastAPIの `response_model` パラメータを使用し、OpenAPIドキュメントも自動生成される。

### 3-2. N+1クエリ解消

**対象:** `backend/app/scoring/engine.py`, `backend/app/scoring/factors.py`

現状: 1レース18頭 × 8ファクター = 144+個のDBクエリ。

改善:
1. `ScoringEngine.predict_race()` で、全エントリの `Horse`, `Result`, 関連 `Race` をバッチプリロード
2. プリロードデータを dict に格納: `{horse_id: Horse}`, `{horse_id: [Result]}` 等
3. 各 factor 関数のシグネチャを変更: `db: Session` → プリロードデータを受け取る
4. 目標: 144+クエリ → 約10クエリ (馬一覧, 結果一覧, 関連レース, エントリー等のバッチ取得)

### 3-3. ScoringEngine のスコアリングと永続化の分離

**対象:** `backend/app/scoring/engine.py` (L113-126)

- `predict_race()` → スコア計算のみ。`list[Prediction]` オブジェクトを返す (未永続化)
- DB保存 (既存Prediction削除 + 新規追加) は呼び出し元 (`FetchService`) の責任に

### 3-4. DBインデックス追加

**対象:** `backend/app/models/` 内の各モデル

```python
# Result
__table_args__ = (Index('ix_result_horse_race', 'horse_id', 'race_id'),)

# Race
Index('ix_race_venue', 'venue')
Index('ix_race_distance', 'distance')

# Entry
__table_args__ = (Index('ix_entry_race_horse', 'race_id', 'horse_id'),)

# Horse
Index('ix_horse_sire', 'sire')
Index('ix_horse_dam_sire', 'dam_sire')
```

### 3-5. config の pydantic-settings 移行

**対象:** `backend/app/config.py`

`Settings` クラスを `pydantic_settings.BaseSettings` に移行:
- `DATABASE_URL`, `OPENWEATHER_API_KEY` (既存)
- `CORS_ORIGINS: list[str]` (段階1で追加済み)
- `.env` ファイルの自動読み込み

`requirements.txt` に `pydantic-settings` を追加。

### 3-6. fetch ルーターの進捗管理改善

**対象:** `backend/app/routers/fetch.py`

```python
@dataclass
class FetchProgress:
    status: str = "idle"
    step: int = 0
    total_steps: int = 7
    message: str = ""
    error: str | None = None

_progress = FetchProgress()
_progress_lock = threading.Lock()
```

グローバル dict の直接操作を dataclass + ロックに置き換え。

### 3-7. 未使用 PredictionService の削除

**対象:** `backend/app/services/prediction_service.py`

ランタイムでどのルーターからも使用されていない薄いラッパー。削除する。

### 検証

- `make test` 全テストパス
- `make lint` エラーなし
- `GET /api/races`, `GET /api/races/{id}/predictions` のレスポンス形状が Pydantic モデルと一致
- スコアリング結果が変更前と同一 (N+1解消は内部最適化のため)

---

## 段階4: フロントエンド改善

**目的:** コンポーネント分割、共通UI部品の抽出、型安全性の向上、データフェッチ層の改善。

**重要:** 全てのフロントエンド変更は `DESIGN.md`（SmartHR Design System）に準拠すること。以下のデザイントークンを厳守する:
- **カラー:** Product Main `#0077c7`、Text Black `#23221e`、Text Grey `#706d65`、Background `#f8f7f6`、Border `#d6d3d0`、Danger `#e01e5a`、Link `#0071c1`。ニュートラルカラーは Stone 系ウォームグレー
- **フォント:** `AdjustedYuGothic, "Yu Gothic", YuGothic, "Hiragino Sans", sans-serif` + `@font-face` トリック
- **サイズ・間隔:** 8px ベーススペーシング、Body 16px、line-height 1.5
- **コンポーネント:** ボタン角丸 6px、テーブルヘッダー背景 `#edebe8`、入力欄ボーダー `#d6d3d0`
- **禁止:** ブランドカラー `#00c4cc` をUI要素に使わない、純粋な `#000000` や `#808080` を使わない

現在のTailwind + daisyUIのスタイリングをSmartHRデザイントークンに置き換える。daisyUIのプリセットクラス（`badge-success` 等）はカスタムユーティリティまたはSmartHRトークンベースのクラスに移行する。

### 4-0. SmartHR デザイントークンの導入

**新規:** `frontend/src/styles/smarthr-tokens.css` — SmartHR Design System のCSSカスタムプロパティ定義

```css
:root {
  --color-main: #0077c7;
  --color-danger: #e01e5a;
  --color-warning: #ffcc17;
  --color-link: #0071c1;
  --color-text-black: #23221e;
  --color-text-grey: #706d65;
  --color-text-disabled: #c1bdb7;
  --color-bg: #f8f7f6;
  --color-surface: #ffffff;
  --color-border: #d6d3d0;
  --color-head: #edebe8;
  --color-over-bg: #f2f1f0;
  --radius-m: 6px;
  --space-xs: 4px;
  --space-s: 8px;
  --space-m: 16px;
  --space-l: 24px;
  --space-xl: 32px;
  --shadow-1: 0 2px 4px rgba(0,0,0,0.1);
  --shadow-2: 0 4px 8px rgba(0,0,0,0.15);
}
```

**変更:** `frontend/src/index.css` — `@font-face` で AdjustedYuGothic を定義、`body` に SmartHR フォントスタック適用

**変更:** `frontend/tailwind.config.js` — `theme.extend` にSmartHRトークンを追加し、daisyUIテーマを上書き

### 4-1. 共通コンポーネント抽出

SmartHRデザイントークンを使用して構築:

- `frontend/src/components/Alert.tsx` — `variant: "error" | "warning" | "info"` を受け取る共通アラート。SmartHR Danger/Warning カラー使用 (5箇所以上の重複を解消)
- `frontend/src/components/Breadcrumb.tsx` — `items: {label: string, to?: string}[]` を受け取る共通パンくず。SmartHR Text Grey + Link カラー使用 (RaceDetail L121-132, HorseDetail L163-176 の重複を解消)
- `frontend/src/components/GradeBadge.tsx` — グレードバッジ表示の統一。SmartHR Danger/Warning/Main カラー使用 (RaceCard のマップを正とし、RaceDetail のインライン三項演算子を置き換え)

### 4-2. インラインコンポーネントの独立ファイル化

- `frontend/src/components/FinishDotChart.tsx` — HorseDetail.tsx (L24-50) から分離
- `frontend/src/components/PedigreeTree.tsx` — HorseDetail.tsx (L53-95) から分離
- `frontend/src/components/Header.tsx` — App.tsx から分離
- `frontend/src/components/Footer.tsx` — App.tsx から分離

### 4-3. 型安全性の向上

**対象:** `frontend/src/types/index.ts`

- `course_type: string` → `"芝" | "ダート"`
- `track_condition: string | null` → `"良" | "稍重" | "重" | "不良" | null`
- `grade: string` → `"G1" | "G2" | "G3"`
- `FetchProgress.status: string` → `"idle" | "running" | "completed" | "error"`
- 未使用型 `ApiResponse<T>`, `Entry` を削除

### 4-4. FetchButton の API 統一

**対象:** `frontend/src/components/FetchButton.tsx`

- 直接 `fetch()` (L28, L57) → `useApi` の `fetchApi` を使用
- ポーリング中のエラー処理追加: リトライ上限 (5回連続失敗でエラー表示)

### 4-5. useApi のバグ修正

**対象:** `frontend/src/hooks/useApi.ts`

- 並行リクエスト時のエラー状態上書き問題: `setError(null)` (L13) が先行リクエストのエラーを消してしまう → `loadingCount` と同様にエラーもカウントベースに
- `AbortController` によるアンマウント時のリクエストキャンセル追加

### 4-6. React Error Boundary 追加

**新規:** `frontend/src/components/ErrorBoundary.tsx`

App.tsx の `<BrowserRouter>` 内に配置。ランタイムエラー時に白画面ではなくフォールバックUIを表示。

### 4-7. 小さな修正

- App.tsx: 未使用 `Link` インポートを削除
- ScoreChart.tsx: `style={{ minHeight: '300px' }}` → `className="min-h-[300px]"`
- ScoreTable.tsx: 馬番カラム (`pred.rank` 表示) の修正

### 4-8. daisyUI の SmartHR カラーへの置き換え

現在のdaisyUIカラープリセット（`badge-success`, `badge-warning`, `badge-error`, `btn-primary` 等）をSmartHRトークンベースのTailwindクラスまたはインラインスタイルに置き換える。

移行の方針:
- `badge-success` → `bg-[#0077c7] text-white` (グレード G3、連対など)
- `badge-warning` → `bg-[#ffcc17] text-[#23221e]` (グレード G2、1着バッジなど)
- `badge-error` → `bg-[#e01e5a] text-white` (グレード G1、重馬場など)
- `btn-primary` → `bg-[#0077c7] text-white font-bold rounded-[6px]`
- 背景色: `bg-[#f8f7f6]` (ページ背景), `bg-white` (カード/テーブル行)
- テキスト: `text-[#23221e]` (本文), `text-[#706d65]` (補助テキスト)
- ボーダー: `border-[#d6d3d0]`
- テーブルヘッダー: `bg-[#edebe8]`

daisyUI を完全に削除するのではなく、カラー定義のみ SmartHR トークンに移行し、ユーティリティクラスの基本的なレイアウトサポートは維持する。

### 検証

- `npm run build` エラーなし
- ブラウザでダッシュボード、レース詳細、馬詳細の各ページを確認
- TypeScript コンパイルエラーなし
- SmartHR カラー適用の目視確認: 背景 `#f8f7f6`、テキスト `#23221e`、ボタン `#0077c7`
- 游ゴシックフォントが正しく適用されているか確認（Windows / macOS）
- `daisyUI` のカラープリセットクラス (`badge-success` 等) が残存していないことを確認

---

## 段階5: テスト補強

**目的:** テストカバレッジの向上とテストコードの品質改善。

### 5-1. テストヘルパーの共通化

**新規:** `backend/tests/factories.py`

3ファイルで重複している `_make_race()`, `_make_horse()`, `_make_result()` を統合。既存テストファイルのローカル定義を削除し、`factories` からインポート。

### 5-2. インラインHTMLフィクスチャの外部化

**新規ディレクトリ:** `backend/tests/fixtures/`

`test_scrapers.py` (L20-252) の230行以上のインラインHTML文字列を個別ファイルに分離:
- `shutuba.html` — 出走表ページ
- `horse_profile.html` — 馬プロフィールページ
- `horse_results.html` — 馬成績テーブル
- `pedigree.html` — 血統AJAX応答
- `race_list.html` — レース一覧AJAX応答
- `jra_thisweek.html` — JRA今週のレース

テストでは `Path(__file__).parent / "fixtures" / "xxx.html"` で読み込み。

### 5-3. 不足テストの追加

| テスト対象 | テスト内容 | ファイル |
|---|---|---|
| `FetchService.execute()` | 全7ステップのモック統合テスト | `tests/test_fetch_service.py` |
| `score_jockey` | 会場・グレード別結果データでのスコア計算 | `tests/test_scoring.py` |
| `score_trainer` | 同上 | `tests/test_scoring.py` |
| `score_bloodline` | 兄弟馬の結果データでのスコア計算 | `tests/test_scoring.py` |
| `WeatherClient` | 成功APIレスポンスのモックテスト | `tests/test_scrapers.py` |
| `_position_score` | エッジケース: position 0, 13+, 18 | `tests/test_scoring.py` |

### 5-4. テストの進捗管理修正

**対象:** `backend/tests/test_api_fetch.py`

`fetch_router._progress` の直接操作 → pytest フィクスチャでリセット:

```python
@pytest.fixture(autouse=True)
def reset_progress():
    from app.routers.fetch import _progress
    # dataclass になった _progress をリセット
    _progress.status = "idle"
    _progress.step = 0
    _progress.message = ""
    _progress.error = None
    yield
```

### 5-5. `seed()` の依存注入

**対象:** `backend/app/seed.py`

```python
def seed(db: Session | None = None):
    """サンプルデータの投入。db未指定時は自前でセッション作成。"""
    own_session = db is None
    if own_session:
        db = SessionLocal()
    try:
        # ... existing logic ...
    finally:
        if own_session:
            db.close()
```

テストでの複雑な `SessionLocal` モックが不要になる。

### 検証

- `make test` 全テストパス (新規テスト含む)
- `make lint` エラーなし
- テストカバレッジの向上を確認

---

## 変更対象ファイルまとめ

### バックエンド (新規)
- `app/scrapers/constants.py` — グレード正規化マップ
- `app/schemas/__init__.py`, `race.py`, `horse.py`, `prediction.py`, `fetch.py` — Pydanticモデル
- `tests/factories.py` — テストヘルパー
- `tests/fixtures/*.html` — HTMLフィクスチャ
- `tests/test_fetch_service.py` — FetchService統合テスト

### バックエンド (変更)
- `app/scoring/factors.py` — 重複排除、パラメータ化、シグネチャ変更
- `app/scoring/weights.py` — 定数追加
- `app/scoring/engine.py` — N+1解消、永続化分離
- `app/scrapers/netkeiba.py` — メソッド分割、定数移動、関数公開化
- `app/scrapers/jra.py` — メソッド分割、定数移動
- `app/scrapers/base.py` — (変更なし)
- `app/scrapers/weather.py` — (変更なし)
- `app/services/fetch_service.py` — メソッド分割、Prediction保存責任の移管
- `app/routers/races.py` — Pydanticモデル使用
- `app/routers/horses.py` — Pydanticモデル使用
- `app/routers/fetch.py` — 進捗管理改善、Pydanticモデル使用
- `app/config.py` — pydantic-settings移行
- `app/main.py` — CORS設定変更
- `app/seed.py` — 依存注入
- `app/models/*.py` — インデックス追加
- `tests/test_scrapers.py` — フィクスチャ外部化
- `tests/test_api_races.py`, `test_api_horses.py`, `test_scoring.py` — ファクトリ使用
- `tests/test_api_fetch.py` — 進捗リセット修正

### バックエンド (削除)
- `app/services/prediction_service.py`

### フロントエンド (新規)
- `src/constants/badge.ts`
- `src/components/Alert.tsx`
- `src/components/Breadcrumb.tsx`
- `src/components/GradeBadge.tsx`
- `src/components/FinishDotChart.tsx`
- `src/components/PedigreeTree.tsx`
- `src/components/Header.tsx`
- `src/components/Footer.tsx`
- `src/components/ErrorBoundary.tsx`

### フロントエンド (変更)
- `src/types/index.ts` — ユニオン型化、未使用型削除
- `src/App.tsx` — Header/Footer分離、ErrorBoundary追加、未使用import削除
- `src/pages/RaceDetail.tsx` — 共通コンポーネント使用
- `src/pages/HorseDetail.tsx` — 共通コンポーネント使用、インラインコンポーネント分離
- `src/pages/Dashboard.tsx` — 共通コンポーネント使用
- `src/components/FetchButton.tsx` — useApi使用、エラー処理改善
- `src/components/RaceCard.tsx` — 定数をconstants/badge.tsから使用
- `src/components/ScoreTable.tsx` — 定数をconstants/badge.tsから使用、馬番修正
- `src/components/ScoreChart.tsx` — style属性のTailwind化
- `src/components/WeatherBadge.tsx` — 定数をconstants/badge.tsから使用
- `src/hooks/useApi.ts` — バグ修正、AbortController追加

### 再利用する既存関数・ユーティリティ
- `app/scrapers/base.py: BaseScraper` — スクレイパー基底クラス (変更なし)
- `app/scoring/weights.py: WEIGHTS` — 既存の重み定数 (定数追加のみ)
- `app/database.py: SessionLocal, get_db` — DB接続 (変更なし)
- `tests/conftest.py` — テストDB設定 (変更なし)
