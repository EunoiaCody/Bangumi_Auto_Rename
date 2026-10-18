# AGENTS.md

Developer/agent guide for **Bangumi_Auto_Rename** (Jellyfin-first fork).
User documentation lives in `README.md`; keep that file user-focused.

## 1. Project Overview

A NiceGUI web app that turns downloaded anime/TV/movie folders into a
Jellyfin-compatible layout. Anime metadata comes from **Bangumi (bgm.tv)** first,
with **TMDB** as fallback; live-action content uses TMDB. It runs on port `5999`,
accepts a qBittorrent completion webhook, and transfers files with hardlinks by
default so seeding is never disturbed. It only organizes directories and file
names — it never writes NFO files or artwork.

## 2. Tech Stack

- Python `>=3.10,<4.0` (Docker uses 3.10).
- NiceGUI `>=2.9.1` + FastAPI/Starlette/Uvicorn.
- `requests>=2.32` for Bangumi HTTP.
- `tmdbsimple>=2.9.1` for TMDB.
- `openai>=1.54.0` and `google-genai>=0.8.0` for optional AI mapping.
- `hachoir>=3.3.0` for video duration.
- `structlog>=24.4.0` for logging.
- PDM + `pdm.lock`; pip-compatible `requirements.txt` (hashed, Windows) and
  `requirements_docker.txt` (Linux).

## 3. Project Structure

```text
src/
├── start.py                 # only ui.run() entry, port 5999
├── web.py                   # "/" page + POST /sendTask webhook
├── main_page.py             # header, menus, about dialog
├── task_queue.py            # single-worker queue (qB concurrency safety)
├── qbittorrent.py           # webhook parsing, tags/categories, hash dedupe
├── logger.py                # structlog config
├── __version__.py           # version + dual copyright + URLs
├── config/config_manager.py # CONFIG_DEFAULT / CN_MAP / cm singleton
├── metadata/
│   ├── models.py            # provider-neutral TypedDicts
│   ├── base.py              # provider ABC, HTTP retry/throttle
│   ├── cache.py             # JSON disk cache (TTL)
│   ├── bangumi.py           # search, relations chain, episodes
│   ├── tmdb.py              # TMDB fallback provider
│   └── resolver.py          # provider order, scoring, title-source policy
├── rename/
│   ├── process.py           # orchestration: resolve → map → transfer
│   ├── get_info.py          # legacy `Search` facade over resolver
│   ├── cleaner.py           # pure filename parsing helpers
│   ├── naming.py            # Jellyfin naming rules (no I/O)
│   ├── ai_processor.py      # AI mapping → naming
│   ├── trans.py             # hardlink/copy/move, qB safety
│   └── utils.py             # constants incl. qB temp suffixes
├── ai/                      # OpenAI/Gemini clients, prompts, pydantic models
├── pages/                   # NiceGUI dialogs (config/edit/table/about)
├── component/               # server-side file picker
├── element/                 # red-themed widgets + notify()
└── utils/                   # path constants, JSON/UI helpers

tests/                       # offline pytest suite + manual AI harness
data/                        # runtime state (gitignored)
```

## 4. Build, Run, Test

```bash
# Linux/macOS
pip install -r requirements_docker.txt

# Windows / hashed lock export
pip install -r requirements.txt

# PDM
pdm install

# Run
python -m src.start        # http://127.0.0.1:5999
python start.py
pdm start

# Tests
pytest tests -q
python -m compileall src
```

- There is no build step. Do not add a second `ui.run()`.
- `tests/test_ai_recognition.py` is a manual CLI harness, not a pytest test.

## 5. Code Conventions

- Black formatting; isort profile `black`, `line_length = 79`,
  `length_sort = true`, `force_sort_within_sections = true`.
- Type hints on public functions; basedpyright basic mode in VS Code.
- Logging: `from ..logger import logger`, Chinese bracket prefixes such as
  `[处理任务]`, `[元数据]`, `[AI处理]`, `[处理迁移]`, `[队列]`.
- UI code belongs in `pages/`, `component/`, `element/`; domain logic in
  `rename/`, `metadata/`, `ai/` must not import NiceGUI.
- Per-file failures are non-fatal: log, write a task JSON with `error`, continue.
- Never modify or delete a source file unless the user explicitly selected
  `剪切` (qB safe mode forbids it).
- New files start with:
  ```python
  # SPDX-License-Identifier: GPL-3.0-or-later
  # Copyright (C) 2024 KimigaiiWuyi
  # Copyright (C) 2025 EunoiaCody
  ```

## 6. Architecture

### Request flow

1. NiceGUI `pick_file()` or qB `POST /sendTask`.
2. `qbittorrent.parse_payload` decodes form values, tags/category and hash.
3. `task_queue.enqueue` writes a `queued` task JSON; a single worker runs
   `Rename().process(...)` off the event loop.
4. `process` normalizes the folder name, resolves metadata, builds a
   `{source: target}` mapping, then `Trans` executes it.
5. Task JSON in `data/task/<uuid>.json` drives the UI table.

### Metadata resolution

- `metadata_source=bangumi` (default): for anime, `BangumiProvider.search`
  (`POST /v0/search/subjects`, type 2) → best candidate → `build_series`.
- Bangumi season model: one subject is usually one season; `build_series` walks
  `前传` backwards and `续集` forwards (max 20, cycle-safe), drops `剧场版`,
  assigns `season_number = 1..N` by date, aggregates all SP/OVA into Season 00.
- Episodes: `/v0/episodes?subject_id=...`; main `type=0`, SP `type=1`, OP/ED/PV
  `type>=2`. `ep` becomes `episode_number`; fractional `sort` becomes special.
- Fallback: `MetadataResolver` tries TMDB when Bangumi is unavailable/empty.
  Jikan has been removed.
- `naming_title_source` controls the folder/file title:
  - `auto`: TMDB title if a TMDB match exists, else Bangumi;
  - `bangumi`: always Bangumi;
  - `tmdb`: always TMDB (fallback Bangumi).
- `get_info.Search` is a compatibility shim; keep its public methods.

### Jellyfin naming (`rename/naming.py`)

- Series: `Name (Year)`.
- Season: `Season 01`, `Season 00`.
- Episode: `Name (Year) S01E01 - Title.ext`.
- Movies: `Name (Year)/Name (Year).ext`; multi-part `- part1` / `- cd1`.
- Extras: `extras/`; specials: `Season 00`.
- `legacy` style reproduces the old `Season1/S01E01 - raw.ext` layout.
- **No NFO, no images, no scraping artifacts.**

### Transfer (`rename/trans.py`)

- Modes: `链接` (default), `复制`, `剪切`.
- qB safe mode (`qb_safe_mode=true`) forces `链接` and refuses `剪切`.
- Hardlink only when `st_dev` matches; otherwise `qb_link_fallback`
  (`copy` default, `symlink`, `skip`).
- Existing target: same inode = already done; otherwise skip, never overwrite.
- Copy writes `*.tmp` then `os.replace`.
- Source files are read-only in link/copy modes.

### qBittorrent webhook

`POST /sendTask` accepts
`path/content_path`, `save_path`+`name`, `tags`/`tag`, `category`, `hash`,
`force`, `is_anime`, `is_movie`, `metadata_id`, `wait`.
Returns `202` when queued (default) or `200/500` with `?wait=1`.

### State

`data/config.json`, `data/task/<uuid>.json`, `data/record/<uuid>.json`,
`data/qb_index/<hash>.json`, `data/cache/<provider>/`,
`data/ai_analysis/`, `data/log/BAR.log` (daily rotation). `data/` is gitignored.

## 7. Configuration

Keys are defined in `CONFIG_DEFAULT` + `CN_MAP` in
`src/config/config_manager.py`; add UI rows in `pages/config_page.py`.

New keys: `metadata_source`, `naming_title_source`, `rename_style`,
`filename_title_language`, `bangumi_access_token`, `bangumi_base_url`,
`bangumi_user_agent`, `qb_safe_mode`, `qb_link_fallback`,
`qb_category_anime`, `qb_category_movie`, `qb_category_ignore`.

`ConfigManager.update_config()` automatically adds missing keys and drops
unknown ones. URL keys ending in `_base_url` are normalized. Tokens/API keys
are masked in logs.

## 8. Testing Strategy

Offline pytest suite (no network):

- `tests/test_naming.py` — naming/sanitization/legacy.
- `tests/test_bangumi_provider.py` — fixtures in `tests/fixtures/bangumi/`:
  search ranking, season chain, specials, movie parsing.
- `tests/test_resolver.py` — Bangumi-first, TMDB fallback, title source.
- `tests/test_qbittorrent_payload.py` — decoding, tags/categories, dedupe.
- `tests/test_transfer.py` — hardlink inode, copy fallback, no overwrite,
  qB safe mode refuses cut.
- `tests/test_process_layout.py` — end-to-end mapping tree, no NFO.

Manual AI harness:

```bash
python tests/test_ai_recognition.py --mode auto --path "/path/to/anime" --provider openai
python tests/test_ai_recognition.py --mode save --path "/path/to/anime" --output case.json
python tests/test_ai_recognition.py --mode auto --input case.json --provider gemini
```

Use `tests/example_test_case.json` / `tests/example_expected.json` as fixtures.
AI result fields are now `season` / `episode`; old `tmdb_*` keys are accepted by
a Pydantic `before` validator.

## 9. Deployment

```bash
docker build -t bangumi-auto-rename:0.3.0 .
docker run -d --name bangumi-auto-rename \
  -p 5999:5999 \
  -v /host/media:/media \
  -v /host/bangumi-data:/Bangumi_Auto_Rename/data \
  bangumi-auto-rename:0.3.0
```

- Dockerfile: Python 3.10 slim, installs `requirements_docker.txt`, exposes 5999.
- Persist `data/`; mount media under `docker_mnt` (default `/media`).
- Hardlinks require source and library on the same filesystem.

## 10. Gotchas

- `LICENSE` is GPLv3 verbatim — do **not** edit it. Attribution changes belong in
  `NOTICE`, `README.md`, `pyproject.toml`, `src/__version__.py`, and the UI about
  dialog.
- `pyproject.toml` and `src/__version__.py` must stay in sync (`0.3.0`).
- `requirements.txt` includes Windows-only `pywin32`; Linux users should use
  `requirements_docker.txt`.
- Bangumi API is throttled to ~1 request/sec; seasons are cached on disk.
- Bangumi search is experimental; manual `metadata_id` is the escape hatch.
- qB webhook path is form-encoded; `qbittorrent.decode_form_value` handles the
  `latin1` → UTF-8 case.
- Do not run AI mode with `剪切`; qB safe mode forces hardlinks.
- `Rename.__init__` creates all configured library roots; empty paths fall back
  to the current directory — set paths before running tasks.
- `season_number=0` is specials; never write specials into a normal season.
