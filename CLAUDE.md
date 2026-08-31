# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Japanese horse racing (keiba) graded-stakes prediction system. Scrapes race data from JRA/netkeiba, scores each horse across 8 weighted factors, and displays ranked predictions in a web UI.

## Commands

All commands run via Docker Compose (requires containers to be running):

```bash
make up          # Build & start containers (frontend :5173, backend :8000)
make down        # Stop containers
make test        # Run backend tests: docker compose exec backend pytest
make lint        # Run ruff: docker compose exec backend ruff check .
make seed        # Load sample data: docker compose exec backend python -m app.seed
make clean       # Remove containers + volumes
```

Run a single test file or test function:
```bash
docker compose exec backend pytest tests/test_scrapers.py
docker compose exec backend pytest tests/test_scrapers.py::TestNetkeibaFetchRaceEntries -v
```

Frontend has no test suite yet (`npm run test` is a no-op).

`make seed` loads `fixtures/sample_race.json`, but overrides the sample race's `date` to the next Saturday from the day it runs (via `app.scrapers.jra.get_target_race_dates`) — scoring only ever targets `Race.date >= today` (see `_score_existing_races` below), so a fixed past date would never get a prediction generated for it.

The production batch pipeline does not go through `make`; it runs via the CLI: `docker compose exec backend python -m app.cli fetch|verify|backfill|export` (see **CLI** under Backend below).

## Architecture

**Monorepo with two services** orchestrated by `docker-compose.yml`:

### Backend (`backend/`) — Python 3.12 + FastAPI + SQLAlchemy + SQLite

- **Entry point**: `app/main.py` — FastAPI app with lifespan hook that calls `init_db()`
- **Database**: `app/database.py` — SQLAlchemy engine/session with `Base` declarative base. SQLite stored at `db/keiba.sqlite3`. `init_db()` runs Alembic `upgrade head` to bring the schema to the latest migration; the one exception is in-memory SQLite (tests), which is empty on every new connection and has no file for Alembic to track, so it just uses `Base.metadata.create_all` instead
- **Config**: `app/config.py` — reads `DATABASE_URL` and `OPENWEATHER_API_KEY` from env
- **Models** (`app/models/`): Race, Horse, Jockey, Trainer, Entry, Result, Prediction, Payout — all use string IDs from netkeiba (Payout's id is an autoincrement int; it's keyed by `race_id + bet_type + combination`). Prediction stores JSON `score_details` column
- **Routers** (`app/routers/`):
  - `races.py` — `GET /api/races`, `GET /api/races/{id}`, `GET /api/races/{id}/predictions` (latest batch only, via `latest_prediction_batch()`)
  - `horses.py` — `GET /api/horses/{id}`, `GET /api/horses/{id}/results`
  - `fetch.py` — `POST /api/fetch` (triggers background data fetch), `GET /api/fetch/progress`
  - `stats.py` — `GET /api/stats` — wraps `verification_service.build_stats()` (的中率・回収率)
- **Scoring engine** (`app/scoring/`):
  - `weights.py` — factor weights (must sum to 1.0), data shortage penalty constants
  - `factors.py` — 8 scoring functions (recent_form, same_race, course_aptitude, bloodline, track_condition, jockey, trainer, overall). Each returns 0-100 float, 50.0 = neutral/no data
  - `engine.py` — `ScoringEngine.predict_race()` orchestrates scoring all entries, saves Prediction rows. Applies `DATA_SHORTAGE_PENALTY` (×0.7) when a horse has fewer than `MIN_RACES_FOR_FULL_SCORE` (5) results. `latest_prediction_batch(predictions, as_of=None)` picks the newest `created_at` batch out of a race's Prediction rows (see **Prediction history** below)
- **Scrapers** (`app/scrapers/`):
  - `constants.py` — `GRADE_NORMALIZE` dict (`GⅠ→G1`, `GⅡ→G2`, `GⅢ→G3`, `J・GⅠ→G1`, ASCII variants `GI/GII/GIII` for db.netkeiba.com pages, etc.) and the `GRADE_PATTERN` regex used to find grade markers in race names. Shared by `jra.py` and `netkeiba.py`
  - `base.py` — `BaseScraper`: rate-limited httpx (2s interval, 3 retries with exponential backoff), `fetch(url, encoding=None)`, `parse_html(html)` → BeautifulSoup. Pass `encoding="euc-jp"` when calling netkeiba AJAX endpoints
  - `jra.py` — `JraScraper.fetch_graded_races(target_dates)` scrapes `https://www.jra.go.jp/keiba/thisweek/` for graded races (`<h3>` tags with `(GⅠ)/(GⅡ)/(GⅢ)` patterns). `get_target_race_dates(today)` returns target dates based on day-of-week (Sat→Sat+Sun, Sun→Sun, weekday→next Sat+Sun)
  - `netkeiba.py` — `NetkeibaScraper`. Race IDs encode `YYYY + venue(2) + kai(2) + day(2) + race_num(2)` (e.g. `202605060311`). Venue codes at index 4-5: 01=札幌, 02=函館, 03=福島, 04=新潟, 05=東京, 06=中山, 07=中京, 08=京都, 09=阪神, 10=小倉
    - `fetch_race_list_by_date(date)` — `race_list_sub.html?kaisai_date=YYYYMMDD` → `[{race_id, race_number}]`
    - `fetch_graded_race_ids(start_year, end_year)` — paginates `db.netkeiba.com` race search (pid=race_list) for G1/G2/G3 in the given year range; stops when a page yields no new IDs. Used by `backfill`
    - `fetch_race_entries(race_id)` — parses `shutuba.html?race_id=…` via `table.Shutuba_Table`; cells identified by classes `td.Waku/Umaban/HorseInfo/Kinryo`; skips rows with class `Cancel` or text `取消`; returns `{}` on error
    - `fetch_odds(race_id)` — unofficial JSON odds API → `{horse_number: win_odds}`; returns `{}` if unsold/missing/unparseable
    - `fetch_horse_profile(horse_id)` — static page for name/birthday/sex + `ajax_horse_pedigree.html?id=…` AJAX endpoint for sire/dam/dam_sire; returns `{}` on error
    - `fetch_horse_results(horse_id, limit=10)` — `ajax_horse_results.html?id=…`; detects column indices from header row text; skips non-numeric 着順 (中止/除外/取消); returns `[]` on error
    - `fetch_race_result(race_id)` — `db.netkeiba.com/race/{race_id}/` full results + payouts page → `{"race": {...}, "results": [...], "payouts": [...]}`; returns `{}` on error. Used by `verify`/`backfill` via `results_service.persist_race_result()`
    - `fetch_race_results_history(race_name, limit=5)` — returns `[]` (still an intentional MVP stub); TODO points to `db.netkeiba.com/?pid=race_search_detail`
  - `weather.py` — `WeatherClient.get_weather(venue)` calls OpenWeatherMap API; returns defaults if API key missing or venue unknown
- **Services** (`app/services/`):
  - `fetch_service.py` — `FetchService.execute()` 7-step pipeline with progress callback:
    1. Determine target dates
    2. JRA graded races + netkeiba `fetch_race_list_by_date()` per date; match by `race_number` to assign `race_id`
    3. `fetch_race_entries()` → `_persist_race_entries()` — upserts Race/Horse/Jockey/Trainer/Entry; also `fetch_odds()` → `_persist_odds()` for the same race
    4. `fetch_horse_profile()` per horse → `_persist_horse_profile()` — updates Horse.sire/dam/dam_sire/sex/birthday
    5. `fetch_horse_results()` per horse → `_persist_horse_results()` — creates Result rows; creates stub Race when FK target is missing
    6. `get_weather()` per venue → updates `Race.weather`
    7. `_score_existing_races()` — scores every `Race` with `date >= today` (not just the races just fetched); final `db.commit()`
    - Falls back to scoring existing DB data if JRA returns no races (off-season/scraper failure)
  - `results_service.py` — `persist_race_result()` upserts one race's full results + Payout rows from `NetkeibaScraper.fetch_race_result()`. Shared foundation for `verify` (WP6) and `backfill` (WP7). Only flushes; commit is the caller's responsibility
  - `collection_service.py` — batch collection loop shared by `verify`/`backfill`: `select_verify_targets()` / `select_uncollected_race_ids()` pick target race IDs (payout presence = "already collected"), `verify_race_results()` / `backfill_race_results()` drive `results_service.persist_race_result()` one race at a time with a per-race commit, so a re-run only chases what's still missing
  - `verification_service.py` — `build_stats()` computes 的中率・回収率. Bet rule (fixed spec): for each race, 100円単勝 + 100円複勝 on the ◎ (rank-1) pick; a race only counts once its Win/Place Payout rows and a pre-race Prediction batch (`created_at.date() <= race.date`) both exist
  - `export_service.py` — `export_static_json()` writes the GitHub Pages static data set (`meta.json`, `races.json`, `races/{id}.json`, `horses/{id}.json`, `stats.json`) that `frontend/src/api/staticRoutes.ts` reads in the public build; read-only, never commits
- **Alembic** (`backend/alembic/`, sibling of `app/`): schema changes go through migrations, not `create_all`. Workflow: edit the SQLAlchemy model → `docker compose exec backend alembic revision --autogenerate -m "..."` → review the generated file under `alembic/versions/` → `init_db()` applies it (`upgrade head`) automatically on next app/CLI startup. `render_as_batch=True` is set because SQLite needs batch mode for column changes. Tests are unaffected — in-memory SQLite still bootstraps via `Base.metadata.create_all`
- **CLI** (`app/cli.py`): the entry point GitHub Actions actually calls (no FastAPI dependency). Four subcommands, exit code 0=success / 1=failure:
  - `fetch` — runs `FetchService.execute()` (weekly entries + odds + predictions)
  - `verify [--days 8]` — fetches confirmed results/payouts for races from `days` ago through yesterday
  - `backfill [--years 5 | --from Y --to Y]` — bulk-collects past JRA graded race results; already-collected races are skipped
  - `export --out <dir>` — writes the static JSON set via `export_service.export_static_json()`
  - `verify`/`backfill` log per-race failures as WARNING and keep going; they only return 1 if *zero* races were saved (signals total scraper breakage, not a few flaky pages)
- **Tests** (`tests/`): pytest with in-memory SQLite. `conftest.py` uses SAVEPOINT rollback pattern per test. Uses `TestClient` for API tests. Scraper tests patch `BaseScraper.fetch()` with `AsyncMock` returning inline HTML fixture strings
- **Linting**: ruff (config in `pyproject.toml`) — rules: E, F, I, W, UP, B; line-length 88; target py312

### Frontend (`frontend/`) — React 18 + Vite + TypeScript + TailwindCSS

Design system is the "競馬新聞エディトリアル" (racing-newspaper editorial) look specified in `DESIGN.md` — no daisyUI, no card/shadow styling; paper background, hairline rules, JRA post-position colors, and 印(◎○▲△) marks driven by CSS variables + Tailwind theme tokens.

- **Entry**: `src/main.tsx` → `src/App.tsx` (react-router-dom with BrowserRouter; nav is 番組表/的中実績)
- **Pages**: Dashboard (番組表 — race list grouped by date + local-only fetch button), RaceDetail (馬柱 — Umabashira entry columns + per-horse factor breakdown), HorseDetail (past results), Stats (的中実績 — 的中率/回収率 summary + cumulative return Chart.js line chart + 回顧 row table)
- **Components**: `Umabashira.tsx` (the vertical-column race-card signature component from DESIGN.md §4), `FetchButton.tsx` (triggers `POST /api/fetch`, polls progress; local dev only)
- **API layer**: `src/hooks/useApi.ts` (`apiGet`/`useResource`) + `src/api/staticRoutes.ts`. When `VITE_DATA_MODE=static` (the GitHub Pages build), requests are rewritten to the static JSON files under `frontend/public/data/` written by `export_service.export_static_json()` instead of hitting `/api` — the public site never talks to a FastAPI backend
- **Proxy**: Vite dev server proxies `/api` to `http://backend:8000` (configured in `vite.config.ts`)

### Data Flow

Local/dev (dynamic mode, `FastAPI` backend live):
1. User clicks "Fetch" → `POST /api/fetch` → `FetchService.execute()` runs as background task
2. FetchService: JRA graded race list → netkeiba race_id lookup → entries + odds per race → horse profiles → horse results → weather → scores every `Race` with `date >= today`
3. Predictions stored in DB → frontend polls `/api/fetch/progress`, then loads `/api/races/{id}/predictions`

Production (GitHub Pages, static mode) — see **CI/CD** below: the `pipeline.yml` workflow runs `app.cli fetch`/`verify` against the committed SQLite DB, then `app.cli export` writes static JSON that the frontend build reads with no backend server involved at request time.

## Prediction history

- `ScoringEngine.predict_race()` never deletes old `Prediction` rows — every run appends a new batch (all rows sharing one `created_at` timestamp) so past predictions stay available for answer-checking (答え合わせ)
- `created_at` is the batch identifier; `latest_prediction_batch(predictions, as_of=None)` picks the rows with the max `created_at` (optionally capped to batches created on/before `as_of`, so a batch generated after a race has already run doesn't leak into verification)
- Scoring only ever targets `Race.date >= date.today()` (`fetch_service._score_existing_races()`) — a race dated in the past never gets a new prediction batch, which is why `app/seed.py` relativizes the sample race's date (see Commands above)

## CI/CD

- **`.github/workflows/ci.yml`**: on every push/PR — backend job runs `ruff check .` + `pytest`; frontend job runs `npm run build` (type-check + Vite build). No scraping, no DB writes
- **`.github/workflows/pipeline.yml`**: the production pipeline. Scheduled in JST via UTC cron: Saturday 6:00 JST (`fetch` — entries/odds → predictions), Monday 6:00 JST (`verify --days 8` — results/payouts → answer-checking). Also runs `export-only` on pushes touching `frontend/**`/`backend/**`/`db/**`, and supports manual `workflow_dispatch` with `fetch`/`verify`/`backfill`/`export-only` modes. Steps: run the CLI subcommand against `db/keiba.sqlite3` → commit the DB back to `main` (skipped for `export-only`) → `app.cli export` → build frontend with `VITE_DATA_MODE=static` → deploy to GitHub Pages. Concurrency group `pipeline` serializes runs so `fetch` and `verify` never race each other
- `db/keiba.sqlite3` is committed to the repo and updated in place by the pipeline — there is no separate production database

## Key Conventions

- All text in the UI and code comments is Japanese (日本語)
- Horse racing domain terms: 勝率(win rate), 連対率(top-2 rate), 複勝率(top-3 rate), 上がり3F(last 3 furlongs time), 馬場状態(track condition: 良/稍重/重/不良), 芝/ダート(turf/dirt)
- Entity IDs come from netkeiba (string format)
- Scoring factors return 50.0 as neutral when no data exists
- Grade normalisation: `GⅠ→G1`, `GⅡ→G2`, `GⅢ→G3`, `J・GⅠ→G1` etc. (defined in the `GRADE_NORMALIZE` dict in `app/scrapers/constants.py`, shared by `jra.py` and `netkeiba.py`)
- `fetch_race_results_history()` is intentionally stubbed — `score_same_race` returns 50.0 until historical data accumulates from repeated fetches
