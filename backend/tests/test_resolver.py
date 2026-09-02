"""
Unit tests for BookResolver: title normalisation, library presence checks
and the combined resolve_book call.  No live services required.
"""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from app.resolver import BookResolver, _norm, _title_variants


class _FakeRelease:
    def __init__(self, title: str, rejected: bool = False):
        self.title = title
        self.rejected = rejected

    def to_dict(self) -> dict:
        return {
            "guid": f"guid-{self.title}",
            "title": self.title,
            "indexer": "MAM",
            "protocol": "torrent",
            "size_mb": 1.5,
            "download_url": "http://prowlarr/dl",
            "rejected": self.rejected,
            "reject_reason": "too small" if self.rejected else None,
        }


def _make_resolver(library_books=None, audiobooks_dir="/nonexistent", search=None) -> BookResolver:
    calibre = MagicMock()
    calibre.get_library_books.return_value = library_books or []
    prowlarr = MagicMock()
    prowlarr.search_releases = search or AsyncMock(return_value=([], []))
    return BookResolver(prowlarr=prowlarr, calibre_library=calibre, audiobooks_dir=audiobooks_dir)


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def test_norm_strips_punctuation_and_case():
    assert _norm("The Left Hand of Darkness!") == "the left hand of darkness"
    assert _norm("Ender's Game") == "enders game"


def test_title_variants_handles_subtitles_parens_and_articles():
    v = _title_variants("The Deer Park: A Novel (Reissue)")
    assert "the deer park" in v
    assert "deer park" in v
    assert "the deer park a novel" in v
    assert "" not in v


# ---------------------------------------------------------------------------
# Presence checks
# ---------------------------------------------------------------------------

def test_check_in_calibre_matches_title_and_author():
    r = _make_resolver(library_books=[{"title": "Dune", "author": "Frank Herbert"}])
    assert asyncio.run(r.check_in_calibre("Dune", "Frank Herbert")) == "Dune"
    assert asyncio.run(r.check_in_calibre("Dune", "Herbert Frank")) == "Dune"  # word-set match
    assert asyncio.run(r.check_in_calibre("Dune", "")) == "Dune"  # empty author → title only
    assert asyncio.run(r.check_in_calibre("Dune", "Someone Else")) is None
    assert asyncio.run(r.check_in_calibre("Neuromancer", "Frank Herbert")) is None


def test_check_in_calibre_fails_open_on_library_error():
    r = _make_resolver()
    r.calibre_library.get_library_books.side_effect = RuntimeError("calibredb exploded")
    assert asyncio.run(r.check_in_calibre("Dune", "Frank Herbert")) is None


def test_check_in_audiobooks_matches_author_dash_title_dirs(tmp_path: Path):
    (tmp_path / "Frank Herbert - Dune").mkdir()
    (tmp_path / "Ursula K. Le Guin - The Left Hand of Darkness").mkdir()
    (tmp_path / "stray-file.txt").write_text("x")
    r = _make_resolver(audiobooks_dir=str(tmp_path))

    assert asyncio.run(r.check_in_audiobooks("Dune", "Frank Herbert")) == "Dune"
    assert asyncio.run(r.check_in_audiobooks("Left Hand of Darkness", "")) == "The Left Hand of Darkness"
    assert asyncio.run(r.check_in_audiobooks("Dune", "Someone Else")) is None
    assert asyncio.run(r.check_in_audiobooks("Missing", "")) is None


def test_check_in_audiobooks_missing_dir_returns_none():
    r = _make_resolver(audiobooks_dir="/definitely/not/here")
    assert asyncio.run(r.check_in_audiobooks("Dune", "Frank Herbert")) is None


# ---------------------------------------------------------------------------
# resolve_book
# ---------------------------------------------------------------------------

def test_resolve_book_combines_searches_and_presence(tmp_path: Path):
    (tmp_path / "Frank Herbert - Dune").mkdir()

    async def search(title, author, content_type="ebook"):
        if content_type == "ebook":
            return [_FakeRelease("Dune.epub")], [_FakeRelease("Dune.tiny", rejected=True)]
        return [_FakeRelease("Dune.m4b")], []

    r = _make_resolver(
        library_books=[{"title": "Dune", "author": "Frank Herbert"}],
        audiobooks_dir=str(tmp_path),
        search=search,
    )
    resp = asyncio.run(r.resolve_book("Dune", "Frank Herbert"))

    assert [x.title for x in resp.ebook_accepted] == ["Dune.epub"]
    assert [x.title for x in resp.ebook_rejected] == ["Dune.tiny"]
    assert resp.ebook_rejected[0].reject_reason == "too small"
    assert [x.title for x in resp.audiobook_accepted] == ["Dune.m4b"]
    assert resp.audiobook_rejected == []
    assert resp.calibre_title == "Dune"
    assert resp.audiobooks_title == "Dune"


def test_resolve_book_searches_both_content_types_once():
    search = AsyncMock(return_value=([], []))
    r = _make_resolver(search=search)
    asyncio.run(r.resolve_book("Dune", "Frank Herbert"))

    kinds = sorted(c.kwargs["content_type"] for c in search.call_args_list)
    assert kinds == ["audiobook", "ebook"]
    for c in search.call_args_list:
        assert c.args == ("Dune", "Frank Herbert")


def test_resolve_book_propagates_search_failure():
    search = AsyncMock(side_effect=RuntimeError("prowlarr down"))
    r = _make_resolver(search=search)
    try:
        asyncio.run(r.resolve_book("Dune", "Frank Herbert"))
    except RuntimeError as exc:
        assert "prowlarr down" in str(exc)
    else:
        raise AssertionError("expected resolve_book to raise")
