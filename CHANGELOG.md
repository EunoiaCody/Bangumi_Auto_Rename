# Changelog

## 0.3.0

### Added

- Bangumi (bgm.tv) metadata provider: search, subject relations (`前传`/`续集`),
  seasons, episodes, specials and extras.
- `MetadataResolver` with Bangumi-first / TMDB-fallback policy and configurable
  title source.
- Jellyfin naming: `Series (Year)/Season 01/Series (Year) S01E01 - Title.ext`,
  `Season 00`, `extras/`, movie `Name (Year)/Name (Year).ext`.
- qBittorrent webhook parsing for tags/categories/infohash, duplicate
  suppression, single-worker queue and status records.
- Hardlink-first transfer with `st_dev` preflight, cross-device fallback
  (`copy` default), target-exists protection and source protection.
- Offline pytest suite and Bangumi fixtures.
- Copyright attribution for EunoiaCody; original KimigaiiWuyi copyright kept.
- `NOTICE` with GPLv3 modification notice.

### Changed

- Anime metadata defaults to Bangumi; TMDB is fallback (non-anime still TMDB).
- AI result fields generalized: `maps_to_seasons`, `season`, `episode`; legacy
  `tmdb_*` JSON remains readable.
- README rewritten around Jellyfin and qBittorrent.
- `requires-python` raised to `>=3.10`.
- `requests` added explicitly; `jikanpy-v4` removed.
- Version unified to `0.3.0`.

### Removed

- Jikan runtime fallback and dependency.
- All NFO/artwork generation (the project only organizes files; Jellyfin handles
  scraping).

### Fixed

- Explicit anime/movie tags now take precedence over the media-type heuristic.
- Hardlink failures due to `EXDEV` fall back to the configured strategy.
- qBittorrent temporary files (`.part`, `.!qB`, padding files) are ignored.
