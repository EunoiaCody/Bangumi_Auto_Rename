from pathlib import Path

from src import qbittorrent


def test_decode_latin1_wrapped_utf8():
    value = "测试".encode("utf-8").decode("latin1")
    assert qbittorrent.decode_form_value(value) == "测试"


def test_parse_payload_and_tags():
    task = qbittorrent.parse_payload(
        {
            "path": "/media/anime/Test",
            "tags": "anime, 2020",
            "category": "anime",
            "hash": "ABC123",
            "name": "Test",
        }
    )
    assert task.path == Path("/media/anime/Test")
    assert task.tags == ["anime", "2020"]
    assert task.category == "anime"
    assert task.torrent_hash == "abc123"


def test_classify_tags_and_ignore(monkeypatch):
    monkeypatch.setattr(
        qbittorrent.cm,
        "get_config",
        lambda key: {
            "qb_category_anime": "anime",
            "qb_category_movie": "movie",
            "qb_category_ignore": "no_process",
        }.get(key, ""),
    )
    assert qbittorrent.classify(
        qbittorrent.QbTask(Path("/x"), tags=["anime"])
    ) == (True, None, False)
    assert qbittorrent.classify(
        qbittorrent.QbTask(Path("/x"), tags=["movie"])
    ) == (None, True, False)
    assert qbittorrent.classify(
        qbittorrent.QbTask(Path("/x"), tags=["no_process"])
    ) == (None, None, True)


def test_duplicate_index(tmp_path, monkeypatch):
    monkeypatch.setattr(qbittorrent, "QB_INDEX_PATH", tmp_path)
    task = qbittorrent.QbTask(Path("/media/anime/Test"), torrent_hash="abc")
    qbittorrent.record_index(task, task_uuid="u1", status="success")
    assert qbittorrent.is_duplicate(task) is True
    assert (
        qbittorrent.is_duplicate(
            qbittorrent.QbTask(Path("/other"), torrent_hash="abc")
        )
        is False
    )
    assert (
        qbittorrent.is_duplicate(
            qbittorrent.QbTask(
                Path("/media/anime/Test"), torrent_hash="abc", force=True
            )
        )
        is False
    )
