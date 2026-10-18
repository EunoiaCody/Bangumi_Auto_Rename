from src.metadata.base import ProviderUnavailable
from src.metadata.resolver import MetadataResolver


def _bangumi_series():
    return {
        "provider": "bangumi",
        "provider_id": 1,
        "media_type": "tv",
        "name": "邦名",
        "names": {"bangumi": "邦名"},
        "name_original": "Bangumi Name",
        "name_cn": "邦名",
        "aliases": ["Bangumi Name"],
        "year": 2020,
        "first_air_date": "2020-01-01",
        "is_anime": True,
        "seasons": [
            {
                "season_number": 1,
                "name": "第一季",
                "episode_count": 1,
                "episodes": [{"episode_number": 1, "name": "第一话"}],
            }
        ],
        "movies": [],
    }


def _tmdb_series():
    return {
        "provider": "tmdb",
        "provider_id": 2,
        "media_type": "tv",
        "name": "TMDB Name",
        "names": {"tmdb": "TMDB Name"},
        "year": 2020,
        "first_air_date": "2020-01-01",
        "is_anime": False,
        "seasons": [],
        "movies": [],
    }


def test_bangumi_first(monkeypatch):
    resolver = MetadataResolver()
    resolver.metadata_source = "bangumi"
    resolver.title_source = "bangumi"
    monkeypatch.setattr(
        resolver.bangumi,
        "search",
        lambda q, y, m: [{"provider_id": 1, "score": 9.0, "name": "邦名"}],
    )
    monkeypatch.setattr(
        resolver.bangumi, "build_series", lambda i: _bangumi_series()
    )
    series = resolver.search_tv("邦名", 2020, True)
    assert series["name"] == "邦名"
    assert series["is_anime"] is True


def test_tmdb_fallback(monkeypatch):
    resolver = MetadataResolver()
    resolver.metadata_source = "bangumi"
    resolver.title_source = "tmdb"
    monkeypatch.setattr(
        resolver.bangumi,
        "search",
        lambda q, y, m: (_ for _ in ()).throw(ProviderUnavailable("down")),
    )
    monkeypatch.setattr(resolver.tmdb, "available", lambda: True)
    monkeypatch.setattr(
        resolver.tmdb,
        "search",
        lambda q, y, m: [
            {"provider_id": 2, "score": 9.0, "name": "TMDB Name"}
        ],
    )
    monkeypatch.setattr(
        resolver.tmdb, "build_series", lambda i: _tmdb_series()
    )
    series = resolver.search_tv("name", 2020, True)
    assert series["name"] == "TMDB Name"


def test_auto_title_source_uses_tmdb_title(monkeypatch):
    resolver = MetadataResolver()
    resolver.metadata_source = "bangumi"
    resolver.title_source = "auto"
    monkeypatch.setattr(
        resolver.bangumi,
        "search",
        lambda q, y, m: [{"provider_id": 1, "score": 9.0, "name": "邦名"}],
    )
    monkeypatch.setattr(
        resolver.bangumi, "build_series", lambda i: _bangumi_series()
    )
    monkeypatch.setattr(resolver.tmdb, "available", lambda: True)
    monkeypatch.setattr(
        resolver.tmdb,
        "search",
        lambda q, y, m: [
            {"provider_id": 2, "score": 9.0, "name": "TMDB Name"}
        ],
    )
    monkeypatch.setattr(
        resolver.tmdb,
        "get_title",
        lambda i, m="tv": {
            "name": "TMDB Name",
            "year": 2020,
            "is_anime": True,
        },
    )
    series = resolver.search_tv("邦名", 2020, True)
    assert series["name"] == "TMDB Name"
    assert series["names"]["bangumi"] == "邦名"
    assert series["names"]["tmdb"] == "TMDB Name"
