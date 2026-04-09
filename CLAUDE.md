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

## Architecture

**Monorepo with two services** orchestrated by `docker-compose.yml`:

### Backend (`backend/`) — Python 3.12 + FastAPI + SQLAlchemy + SQLite

- **Entry point**: `app/main.py` — FastAPI app with lifespan hook that calls `init_db()`
- **Database**: `app/database.py` — SQLAlchemy engine/session with `Base` declarative base. SQLite stored at `db/keiba.sqlite3`. Tables auto-created via `Base.metadata.create_all`
- **Config**: `app/config.py` — reads `DATABASE_URL` and `OPENWEATHER_API_KEY` from env
- **Models** (`app/models/`): Race, Horse, Jockey, Trainer, Entry, Result, Prediction — all use string IDs from netkeiba. Prediction stores JSON `score_details` column
- **Routers** (`app/routers/`):
  - `races.py` — `GET /api/races`, `GET /api/races/{id}`, `GET /api/races/{id}/predictions`
  - `horses.py` — `GET /api/horses/{id}`, `GET /api/horses/{id}/results`
  - `fetch.py` — `POST /api/fetch` (triggers background data fetch), `GET /api/fetch/progress`
- **Scoring engine** (`app/scoring/`):
  - `weights.py` — factor weights (must sum to 1.0), data shortage penalty constants
  - `factors.py` — 8 scoring functions (recent_form, same_race, course_aptitude, bloodline, track_condition, jockey, trainer, overall). Each returns 0-100 float, 50.0 = neutral/no data
  - `engine.py` — `ScoringEngine.predict_race()` orchestrates scoring all entries, saves Prediction rows. Applies `DATA_SHORTAGE_PENALTY` (×0.7) when a horse has fewer than `MIN_RACES_FOR_FULL_SCORE` (5) results
- **Scrapers** (`app/scrapers/`):
  - `base.py` — `BaseScraper`: rate-limited httpx (2s interval, 3 retries with exponential backoff), `fetch(url, encoding=None)`, `parse_html(html)` → BeautifulSoup. Pass `encoding="euc-jp"` when calling netkeiba AJAX endpoints
  - `jra.py` — `JraScraper.fetch_graded_races(target_dates)` scrapes `https://www.jra.go.jp/keiba/thisweek/` for graded races (`<h3>` tags with `(GⅠ)/(GⅡ)/(GⅢ)` patterns). `get_target_race_dates(today)` returns target dates based on day-of-week (Sat→Sat+Sun, Sun→Sun, weekday→next Sat+Sun)
  - `netkeiba.py` — `NetkeibaScraper` with 5 methods. Race IDs encode `YYYY + venue(2) + kai(2) + day(2) + race_num(2)` (e.g. `202605060311`). Venue codes at index 4-5: 01=札幌, 02=函館, 03=福島, 04=新潟, 05=東京, 06=中山, 07=中京, 08=京都, 09=阪神, 10=小倉
    - `fetch_race_list_by_date(date)` — `race_list_sub.html?kaisai_date=YYYYMMDD` → `[{race_id, race_number}]`
    - `fetch_race_entries(race_id)` — parses `shutuba.html?race_id=…` via `table.Shutuba_Table`; cells identified by classes `td.Waku/Umaban/HorseInfo/Kinryo`; skips rows with class `Cancel` or text `取消`; returns `{}` on error
    - `fetch_horse_profile(horse_id)` — static page for name/birthday/sex + `ajax_horse_pedigree.html?id=…` AJAX endpoint for sire/dam/dam_sire; returns `{}` on error
    - `fetch_horse_results(horse_id, limit=10)` — `ajax_horse_results.html?id=…`; detects column indices from header row text; skips non-numeric 着順 (中止/除外/取消); returns `[]` on error
    - `fetch_race_results_history(race_name, limit=5)` — returns `[]` (MVP stub); TODO points to `db.netkeiba.com/?pid=race_search_detail`
  - `weather.py` — `WeatherClient.get_weather(venue)` calls OpenWeatherMap API; returns defaults if API key missing or venue unknown
- **Services** (`app/services/`):
  - `fetch_service.py` — `FetchService.execute()` 7-step pipeline with progress callback:
    1. Determine target dates
    2. JRA graded races + netkeiba `fetch_race_list_by_date()` per date; match by `race_number` to assign `race_id`
    3. `fetch_race_entries()` → `_persist_race_entries()` — upserts Race/Horse/Jockey/Trainer/Entry
    4. `fetch_horse_profile()` per horse → `_persist_horse_profile()` — updates Horse.sire/dam/dam_sire/sex/birthday
    5. `fetch_horse_results()` per horse → `_persist_horse_results()` — creates Result rows; creates stub Race when FK target is missing
    6. `get_weather()` per venue → updates `Race.weather`
    7. `ScoringEngine.predict_race()` for all races; final `db.commit()`
    - Falls back to scoring existing DB data if JRA returns no races (off-season/scraper failure)
  - `prediction_service.py` — wraps scoring engine
- **Tests** (`tests/`): pytest with in-memory SQLite. `conftest.py` uses SAVEPOINT rollback pattern per test. Uses `TestClient` for API tests. Scraper tests patch `BaseScraper.fetch()` with `AsyncMock` returning inline HTML fixture strings
- **Linting**: ruff (config in `pyproject.toml`) — rules: E, F, I, W, UP, B; line-length 88; target py312

### Frontend (`frontend/`) — React 18 + Vite + TypeScript + TailwindCSS + daisyUI

- **Entry**: `src/main.tsx` → `src/App.tsx` (react-router-dom with BrowserRouter)
- **Pages**: Dashboard (race list + fetch button), RaceDetail (predictions + score chart), HorseDetail (past results)
- **Components**: RaceCard, ScoreTable, ScoreChart (Chart.js radar), WeatherBadge, FetchButton (with progress polling)
- **API layer**: `src/hooks/useApi.ts` — custom hook wrapping `fetch()` against `/api` prefix
- **Proxy**: Vite dev server proxies `/api` to `http://backend:8000` (configured in `vite.config.ts`)

### Data Flow

1. User clicks "Fetch" → `POST /api/fetch` → `FetchService.execute()` runs as background task
2. FetchService: JRA graded race list → netkeiba race_id lookup → entries per race → horse profiles → horse results → weather → `ScoringEngine.predict_race()` per race
3. Predictions stored in DB → frontend polls `/api/fetch/progress`, then loads `/api/races/{id}/predictions`

## Key Conventions

- All text in the UI and code comments is Japanese (日本語)
- Horse racing domain terms: 勝率(win rate), 連対率(top-2 rate), 複勝率(top-3 rate), 上がり3F(last 3 furlongs time), 馬場状態(track condition: 良/稍重/重/不良), 芝/ダート(turf/dirt)
- Entity IDs come from netkeiba (string format)
- Scoring factors return 50.0 as neutral when no data exists
- Grade normalisation: `GⅠ→G1`, `GⅡ→G2`, `GⅢ→G3`, `J・GⅠ→G1` etc. (defined in `_GRADE_NORMALIZE` dict in `netkeiba.py`)
- `fetch_race_results_history()` is intentionally stubbed — `score_same_race` returns 50.0 until historical data accumulates from repeated fetches
