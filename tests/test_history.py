import sqlite3
import time

from mediaforge.models.task import Task, TaskKind, TaskStatus
from mediaforge.storage.history import HistoryStore
from mediaforge.storage.settings import Settings


def finished_task(name="v.mp4", status=TaskStatus.COMPLETED, **kw):
    t = Task(TaskKind.CONVERT, name, output_format="MP4", **kw)
    t.status, t.finished_at, t.size_bytes, t.message = status, time.time(), 123, "ok"
    return t


def test_add_list_clear(tmp_path):
    h = HistoryStore(tmp_path / "h.db")
    h.add_task(finished_task("a.mp4"))
    h.add_task(finished_task("b.mp4", TaskStatus.FAILED, source_host="cdn.exemplo.com"))
    entries = h.list()
    assert [e.file_name for e in entries] == ["b.mp4", "a.mp4"]
    assert entries[0].status == "Falhou" and entries[0].source_host == "cdn.exemplo.com"
    assert entries[1].operation == "Conversão" and entries[1].output_format == "MP4"
    h.clear()
    assert h.list() == []


def test_persists_across_instances(tmp_path):
    HistoryStore(tmp_path / "h.db").add_task(finished_task("keep.mp4"))
    assert HistoryStore(tmp_path / "h.db").list()[0].file_name == "keep.mp4"


def test_retention_prunes_old_entries(tmp_path):
    h = HistoryStore(tmp_path / "h.db", retention_days=30)
    h.add_task(finished_task("novo.mp4"))
    old = finished_task("velho.mp4")
    old.finished_at = time.time() - 40 * 86400
    h.add_task(old)
    assert h.prune() == 1
    assert [e.file_name for e in h.list()] == ["novo.mp4"]


def test_no_urls_or_secrets_in_database(tmp_path):
    h = HistoryStore(tmp_path / "h.db")
    h.add_task(finished_task("v.mp4", source_host="cdn.exemplo.com"))
    with sqlite3.connect(tmp_path / "h.db") as conn:
        dump = "\n".join(str(row) for row in conn.execute("SELECT * FROM history"))
    for forbidden in ("http", "token", "cookie", "?", "="):
        assert forbidden not in dump.lower()
    cols = {r[1] for r in sqlite3.connect(tmp_path / "h.db").execute("PRAGMA table_info(history)")}
    assert "url" not in cols


def test_settings_roundtrip_and_clamping(tmp_path):
    p = tmp_path / "s.json"
    Settings(output_dir=str(tmp_path), max_download_mb=10).save(p)
    assert Settings.load(p).max_download_mb == 10
    p.write_text('{"max_download_mb": -5, "history_retention_days": 99999, "desconhecido": 1}')
    s = Settings.load(p)
    assert s.max_download_mb == 1 and s.history_retention_days == 3650
    p.write_text("{quebrado")
    assert Settings.load(p).max_download_mb == 4096
