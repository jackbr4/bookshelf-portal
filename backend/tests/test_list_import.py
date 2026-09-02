"""
Unit tests for the list-import extractor: URL fetch guards, trafilatura
cleaning, LLM output parsing and mock mode.  No live services required —
HTTP is served by httpx.MockTransport and the Anthropic client is stubbed.
"""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.list_import import ListExtractor, ExtractionError, MOCK_BOOKS, _tidy
from app.models import BookCandidate


def _make(mock_mode=False, api_key="test-key", max_books=40, max_bytes=2 * 1024 * 1024) -> ListExtractor:
    return ListExtractor(
        api_key=api_key,
        model="claude-haiku-4-5",
        max_books=max_books,
        fetch_timeout=5.0,
        fetch_max_bytes=max_bytes,
        mock_mode=mock_mode,
    )


ARTICLE_HTML = """<!doctype html><html><head><title>Ten Novels to Read This Summer | Example Review</title></head>
<body><nav><a href="/">Home</a><a href="/about">About</a></nav>
<article>
<h1>Ten Novels to Read This Summer</h1>
<p>Every year we ask our critics for the books they can't stop thinking about. Here are their picks,
with a few words on why each one earns a place on your nightstand this summer.</p>
<h2>1. The Left Hand of Darkness by Ursula K. Le Guin</h2>
<p>A meditation on gender and politics on a frozen planet, still startling fifty years on.</p>
<h2>2. Piranesi by Susanna Clarke</h2>
<p>A labyrinthine house, an endless sea, and one of the most tender narrators in recent fiction.</p>
</article>
<aside>Related: The best cookbooks of 2025</aside>
<footer>© Example Review</footer></body></html>"""


def _llm_response(payload, stop_reason="end_turn"):
    """Shape of anthropic Message that _extract reads."""
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="text", text=json.dumps(payload) if not isinstance(payload, str) else payload)],
        usage=SimpleNamespace(input_tokens=100, output_tokens=20),
    )


def _with_stub_llm(extractor: ListExtractor, response):
    """Install a fake AsyncAnthropic on the extractor and return its create mock."""
    create = AsyncMock(return_value=response) if not isinstance(response, Exception) else AsyncMock(side_effect=response)
    extractor._anthropic = SimpleNamespace(messages=SimpleNamespace(create=create))
    return create


def _mock_http(handler):
    """Patch httpx.AsyncClient so the extractor's fetch goes through MockTransport."""
    real = httpx.AsyncClient

    def factory(**kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(**kwargs)

    return patch("app.list_import.httpx.AsyncClient", side_effect=factory)


# ---------------------------------------------------------------------------
# Mock mode
# ---------------------------------------------------------------------------

def test_mock_mode_returns_canned_list_without_network_or_llm():
    ex = _make(mock_mode=True, api_key="")
    books, title = asyncio.run(ex.extract_from_url("https://example.com/list"))
    assert books == MOCK_BOOKS
    assert title
    assert asyncio.run(ex.extract_from_text("anything")) == MOCK_BOOKS
    # Mixed confidence and one missing author, per the handoff spec
    assert {b.confidence for b in books} == {"high", "low"}
    assert any(b.author == "" for b in books)


# ---------------------------------------------------------------------------
# Fetch guards
# ---------------------------------------------------------------------------

def test_fetch_rejects_non_http_url():
    ex = _make()
    with pytest.raises(ExtractionError) as ei:
        asyncio.run(ex.extract_from_url("ftp://example.com/x"))
    assert ei.value.code == "fetch_failed"


def test_fetch_refuses_local_and_private_hosts():
    ex = _make()
    for url in [
        "http://localhost:29254/api/v1/indexer",
        "http://127.0.0.1/",
        "http://[::1]:8080/",
        "http://10.0.0.5/",
        "http://192.168.1.10/",
        "http://172.16.0.1/",
        "http://169.254.169.254/latest/meta-data",
        "http://seedbox.local/",
    ]:
        with pytest.raises(ExtractionError) as ei:
            asyncio.run(ex.extract_from_url(url))
        assert ei.value.code == "fetch_failed", url
        assert "local" in ei.value.message


def test_fetch_refuses_redirects_into_private_hosts():
    ex = _make()

    def handler(req):
        if req.url.host == "example.com":
            return httpx.Response(302, headers={"location": "http://127.0.0.1:29254/api/v1/indexer"})
        return httpx.Response(200, text=ARTICLE_HTML, headers={"content-type": "text/html"})

    with _mock_http(handler):
        with pytest.raises(ExtractionError) as ei:
            asyncio.run(ex.extract_from_url("https://example.com/list"))
    assert ei.value.code == "fetch_failed"
    assert "local" in ei.value.message


def test_fetch_http_error_becomes_fetch_failed():
    ex = _make()
    with _mock_http(lambda req: httpx.Response(403, text="forbidden")):
        with pytest.raises(ExtractionError) as ei:
            asyncio.run(ex.extract_from_url("https://example.com/paywalled"))
    assert ei.value.code == "fetch_failed"
    assert "403" in ei.value.message


def test_fetch_rejects_non_text_content_type():
    ex = _make()
    with _mock_http(lambda req: httpx.Response(200, content=b"%PDF-1.4", headers={"content-type": "application/pdf"})):
        with pytest.raises(ExtractionError) as ei:
            asyncio.run(ex.extract_from_url("https://example.com/list.pdf"))
    assert ei.value.code == "fetch_failed"
    assert "application/pdf" in ei.value.message


def test_fetch_enforces_size_cap_on_body():
    ex = _make(max_bytes=1000)
    big = ("<p>" + "x" * 50 + "</p>") * 100  # ~5.7 KB, no content-length header via MockTransport streaming
    with _mock_http(lambda req: httpx.Response(200, text=big, headers={"content-type": "text/html"})):
        with pytest.raises(ExtractionError) as ei:
            asyncio.run(ex.extract_from_url("https://example.com/huge"))
    assert ei.value.code == "fetch_failed"
    assert "too large" in ei.value.message


def test_fetch_network_error_becomes_fetch_failed():
    ex = _make()

    def boom(req):
        raise httpx.ConnectError("dns fail", request=req)

    with _mock_http(boom):
        with pytest.raises(ExtractionError) as ei:
            asyncio.run(ex.extract_from_url("https://nope.invalid/"))
    assert ei.value.code == "fetch_failed"


def test_fetch_sends_browser_user_agent():
    seen = {}

    def handler(req):
        seen["ua"] = req.headers.get("user-agent", "")
        return httpx.Response(200, text=ARTICLE_HTML, headers={"content-type": "text/html; charset=utf-8"})

    ex = _make()
    _with_stub_llm(ex, _llm_response({"books": []}))
    with _mock_http(handler):
        asyncio.run(ex.extract_from_url("https://example.com/list"))
    assert "Mozilla/5.0" in seen["ua"]


# ---------------------------------------------------------------------------
# Cleaning
# ---------------------------------------------------------------------------

def test_empty_page_is_no_content():
    ex = _make()
    js_shell = "<html><head><title>App</title></head><body><div id='root'></div><script src='/app.js'></script></body></html>"
    with _mock_http(lambda req: httpx.Response(200, text=js_shell, headers={"content-type": "text/html"})):
        with pytest.raises(ExtractionError) as ei:
            asyncio.run(ex.extract_from_url("https://spa.example.com/list"))
    assert ei.value.code == "no_content"


def test_clean_strips_boilerplate_and_returns_title():
    ex = _make()
    text, title = ex._clean(ARTICLE_HTML, "https://example.com/list")
    assert "Left Hand of Darkness" in text
    assert "Piranesi" in text
    assert "Home" not in text and "About" not in text  # nav stripped
    assert "Ten Novels to Read This Summer" in (title or "")


def test_empty_pasted_text_is_no_content():
    ex = _make()
    with pytest.raises(ExtractionError) as ei:
        asyncio.run(ex.extract_from_text("   \n  "))
    assert ei.value.code == "no_content"


# ---------------------------------------------------------------------------
# LLM call + parsing
# ---------------------------------------------------------------------------

def test_extract_from_text_parses_structured_output_and_prompts_correctly():
    ex = _make(max_books=40)
    create = _with_stub_llm(ex, _llm_response({"books": [
        {"title": "  Piranesi ", "author": "Susanna Clarke", "confidence": "high"},
        {"title": "Stoner", "author": "", "confidence": "low"},
        {"title": "piranesi", "author": "susanna clarke", "confidence": "high"},  # dup, different case
    ]}))

    books = asyncio.run(ex.extract_from_text("Some article about Piranesi and Stoner"))

    assert books == [
        BookCandidate(title="Piranesi", author="Susanna Clarke", confidence="high"),
        BookCandidate(title="Stoner", author="", confidence="low"),
    ]
    kwargs = create.call_args.kwargs
    assert kwargs["model"] == "claude-haiku-4-5"
    assert kwargs["output_config"]["format"]["type"] == "json_schema"
    assert "Piranesi and Stoner" in kwargs["messages"][0]["content"]
    assert "up to 40 books" in kwargs["messages"][0]["content"]
    assert "book recommendations" in kwargs["system"]


def test_extract_caps_result_at_max_books():
    ex = _make(max_books=2)
    _with_stub_llm(ex, _llm_response({"books": [
        {"title": f"Book {i}", "author": "A", "confidence": "high"} for i in range(5)
    ]}))
    books = asyncio.run(ex.extract_from_text("five books"))
    assert [b.title for b in books] == ["Book 0", "Book 1"]


def test_missing_api_key_is_not_configured():
    ex = _make(api_key="")
    with pytest.raises(ExtractionError) as ei:
        asyncio.run(ex.extract_from_text("some article"))
    assert ei.value.code == "not_configured"


def test_unparseable_model_output_is_llm_failed():
    ex = _make()
    _with_stub_llm(ex, _llm_response("not json at all"))
    with pytest.raises(ExtractionError) as ei:
        asyncio.run(ex.extract_from_text("some article"))
    assert ei.value.code == "llm_failed"


def test_refusal_is_llm_failed():
    ex = _make()
    _with_stub_llm(ex, _llm_response({"books": []}, stop_reason="refusal"))
    with pytest.raises(ExtractionError) as ei:
        asyncio.run(ex.extract_from_text("some article"))
    assert ei.value.code == "llm_failed"


def test_api_errors_map_to_codes():
    import anthropic

    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")

    ex = _make()
    _with_stub_llm(ex, anthropic.AuthenticationError(
        "bad key", response=httpx.Response(401, request=req), body=None
    ))
    with pytest.raises(ExtractionError) as ei:
        asyncio.run(ex.extract_from_text("article"))
    assert ei.value.code == "not_configured"

    ex = _make()
    _with_stub_llm(ex, anthropic.InternalServerError(
        "boom", response=httpx.Response(500, request=req), body=None
    ))
    with pytest.raises(ExtractionError) as ei:
        asyncio.run(ex.extract_from_text("article"))
    assert ei.value.code == "llm_failed"


def test_url_flow_end_to_end_with_stubbed_llm():
    ex = _make()
    _with_stub_llm(ex, _llm_response({"books": [
        {"title": "The Left Hand of Darkness", "author": "Ursula K. Le Guin", "confidence": "high"},
        {"title": "Piranesi", "author": "Susanna Clarke", "confidence": "high"},
    ]}))
    with _mock_http(lambda req: httpx.Response(200, text=ARTICLE_HTML, headers={"content-type": "text/html; charset=utf-8"})):
        books, title = asyncio.run(ex.extract_from_url("https://example.com/list"))
    assert [b.title for b in books] == ["The Left Hand of Darkness", "Piranesi"]
    assert title and "Ten Novels" in title


def test_tidy_drops_blank_titles():
    out = _tidy([BookCandidate(title="   ", author="X"), BookCandidate(title="Dune", author="Frank  Herbert")])
    assert out == [BookCandidate(title="Dune", author="Frank Herbert", confidence="high")]
