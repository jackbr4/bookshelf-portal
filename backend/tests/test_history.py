"""
Unit tests for HistoryDB.get_recent surfacing calibre_id from the imports
table, which backs the Admin History "In Library" Calibre link.
"""
from app.history import HistoryDB


def test_get_recent_includes_calibre_id_for_imported_ebook(tmp_path):
    db = HistoryDB(str(tmp_path / "history.db"))
    record_id = db.create_download("Dune", "Frank Herbert", "Dune (epub)", "MAM", "torrent", "hash1")
    db.create_import(record_id, "/books/dune.epub", "imported", calibre_id=42)
    db.update_download_status(record_id, "imported")

    items = db.get_recent()
    assert len(items) == 1
    assert items[0]["calibre_id"] == 42


def test_get_recent_calibre_id_is_none_without_import_row(tmp_path):
    db = HistoryDB(str(tmp_path / "history.db"))
    record_id = db.create_download("Moby Dick", "Herman Melville", "Moby Dick", "MAM", "torrent", "hash2", media_type="audiobook")
    db.create_import(record_id, "/audiobooks/Moby Dick", "imported")  # no calibre_id: audiobooks aren't added to Calibre
    db.update_download_status(record_id, "imported")

    items = db.get_recent()
    assert items[0]["calibre_id"] is None


def test_get_recent_calibre_id_is_none_for_error_import(tmp_path):
    db = HistoryDB(str(tmp_path / "history.db"))
    record_id = db.create_download("Broken Book", "Some Author", "Broken Book (epub)", "MAM", "torrent", "hash3")
    db.create_import(record_id, "/books/broken.epub", "error", error="calibredb add failed")
    db.update_download_status(record_id, "error", "calibredb add failed")

    items = db.get_recent()
    assert items[0]["calibre_id"] is None


def test_get_recent_uses_most_recent_imported_row_when_multiple_exist(tmp_path):
    db = HistoryDB(str(tmp_path / "history.db"))
    record_id = db.create_download("Dune", "Frank Herbert", "Dune (epub)", "MAM", "torrent", "hash4")
    db.create_import(record_id, "/books/dune-v1.epub", "error", error="first attempt failed")
    db.create_import(record_id, "/books/dune-v2.epub", "imported", calibre_id=99)
    db.update_download_status(record_id, "imported")

    items = db.get_recent()
    assert items[0]["calibre_id"] == 99
