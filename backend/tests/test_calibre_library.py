"""
Unit test for CalibreLibrary.get_library_books against a minimal real
metadata.db schema, verifying the book id (used to build Calibre-Web links)
comes through correctly.
"""
import sqlite3

from app.calibre_library import CalibreLibrary


def _make_metadata_db(path) -> None:
    conn = sqlite3.connect(str(path))
    conn.executescript("""
        CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT);
        CREATE TABLE authors (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE books_authors_link (book INTEGER, author INTEGER);
        INSERT INTO books (id, title) VALUES (3227, 'Dept. Of Speculation');
        INSERT INTO authors (id, name) VALUES (1, 'Jenny Offill');
        INSERT INTO books_authors_link (book, author) VALUES (3227, 1);
    """)
    conn.commit()
    conn.close()


def test_get_library_books_includes_id(tmp_path):
    _make_metadata_db(tmp_path / "metadata.db")
    lib = CalibreLibrary(library_path=str(tmp_path))
    books = lib.get_library_books()
    assert books == [{"id": 3227, "title": "Dept. Of Speculation", "author": "Jenny Offill"}]


def test_get_library_books_missing_db_returns_empty(tmp_path):
    lib = CalibreLibrary(library_path=str(tmp_path))  # no metadata.db written
    assert lib.get_library_books() == []
