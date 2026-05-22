# Bookshelf Portal — Seedbox Context

This document provides context for Claude Code running on the seedbox at `narvi.whatbox.ca`.

## What This Project Is

A password-protected family-facing web portal for searching and requesting books/series to be added to Bookshelf (a Readarr fork). Books flow:

**Bookshelf → `/home/jackbr4/files/Books` → Calibre (via cron importer)**

## Stack

- **Backend**: FastAPI + Uvicorn (Python 3.12)
- **Frontend**: React + TypeScript + Vite + Bootstrap
- **Container**: Podman (rootless, `--network=host`)
- **CI/CD**: GitHub Actions → SSH → pull/build/replace on push to `main`

## Seedbox Constraints

- **Host**: narvi.whatbox.ca, **User**: jackbr4
- **No sudo access** — rootless Podman only
- App lives at: `~/apps/bookshelf-portal/bookshelf-portal/`
- `.env` lives at: `~/apps/bookshelf-portal/bookshelf-portal/.env`
- Live URL: http://narvi.whatbox.ca:8788

## Key Architecture Decisions

- **Single container**: Dockerfile builds React frontend, copies `dist` to `/app/static`, FastAPI serves it via `StaticFiles` + SPA fallback
- **`--network=host` is required**: Podman's slirp4netns port forwarding (`-p host:container`) does not propagate to external interfaces on this seedbox — host networking is the only working approach
- **Dockerfile CMD uses exec form** `["uvicorn", ...]` (NOT `sh -c`) so uvicorn receives signals correctly and `podman run --replace` works
- **PORT is hardcoded to 8788** in Dockerfile CMD (not an env var) because host networking is used — there is no container/host port mapping to worry about

## Important Files

| File | Purpose |
|------|---------|
| `backend/app/main.py` | FastAPI routes + static file serving |
| `backend/app/bookshelf_client.py` | Readarr API client + mock mode |
| `backend/app/settings.py` | Env var config (pydantic-settings) |
| `frontend/src/routes/RequestRoute.tsx` | Main UI + all toast messages |
| `frontend/src/components/SearchPanel.tsx` | Search box / placeholder text |
| `Dockerfile` | Multi-stage build (node → python) |
| `.github/workflows/deploy.yml` | CI/CD pipeline |

## Deployment Workflow

1. Edit code locally
2. `git push origin main`
3. GitHub Actions auto-deploys (~2–3 min build)
4. Verify at http://narvi.whatbox.ca:8788

## Manual Container Commands

```bash
podman logs bookshelf-request-portal        # view logs
podman logs -f bookshelf-request-portal     # follow logs
podman ps                                   # check running status
podman run --replace ...                    # redeploy manually
```

## Primary Issue to Fix: Goodreads Dependency in Add-Book Flow

Bookshelf (the Readarr fork) uses Goodreads as its metadata source. When Goodreads is down or slow, the **add-book flow fails** because `_fetch_lookup_result` in `bookshelf_client.py` calls `/api/v1/book/lookup` which internally hits Goodreads.

### How the current flow works

1. **Search** (`_lookup_books`): calls `/api/v1/book/lookup` and caches results in `_book_lookup_cache` (10-min TTL, keyed by `foreignBookId`).
2. **Add** (`add_book` → `_fetch_lookup_result`):
   - For **native Bookshelf IDs**: checks `_book_lookup_cache` first. If there's a cache hit, skips the Goodreads call entirely. ✅
   - For **Open Library IDs** (`ol:` prefix) or **Google Books IDs** (`gb:` prefix): **always** does a fresh `/api/v1/book/lookup` call, hitting Goodreads. ❌
   - For **native IDs with cache misses** (e.g. user waits >10 min before clicking Add): also falls back to a fresh lookup. ❌

### Why this is painful

- Goodreads goes down or rate-limits Bookshelf unpredictably.
- Users search fine (Google Books / Open Library fallbacks handle search), but when they click "Add", the add-time lookup to Bookshelf/Goodreads fails, returning a `BOOKSHELF_ERROR` toast.
- The root cause is that `_fetch_lookup_result` needs a full Bookshelf-native lookup result (with `foreignBookId`, `foreignEditionId`, author metadata, etc.) to build the POST payload for `/api/v1/book`. For `ol:`/`gb:` IDs, there's no cached Bookshelf result to reuse.

### Relevant code locations

- `backend/app/bookshelf_client.py`:
  - `_fetch_lookup_result` (line ~482) — the method that triggers the Goodreads-dependent lookup at add time
  - `_lookup_books` (line ~273) — search-time lookup with fallback logic; populates `_book_lookup_cache`
  - `add_book` (line ~155) — calls `_fetch_lookup_result`, then builds the POST payload
  - `_book_lookup_cache` (line ~105) — the 10-min in-memory cache that avoids repeat Goodreads hits for native IDs

### Important constraint: Bookshelf itself requires Goodreads

Even if the portal's lookup call is eliminated, **Bookshelf's own `/api/v1/book` POST internally calls Goodreads** to resolve and store full metadata. If Goodreads is completely down, the add will fail inside Bookshelf regardless of what the portal does. This is a hard limitation of the Readarr/Bookshelf architecture — the portal cannot work around it entirely.

What the portal *can* fix is **unnecessary extra Goodreads calls**: the current code hits Goodreads twice at add time (once for the portal's lookup, once inside Bookshelf). Eliminating the portal's redundant call means fewer failure points and faster adds when Goodreads is slow but not fully down.

### Goal

Reduce or eliminate Goodreads dependency at add time by:
1. Extending or improving cache reuse so add never re-hits Goodreads if the book was recently searched.
2. For `ol:`/`gb:` IDs, try to reuse search-time Bookshelf results if any native ID was found for the same title/author during the search phase.
3. Building a more resilient fallback if Goodreads is truly unavailable at add time (e.g. retry with stripped query, surface a clearer error).

## Other Known Issues / History

- `podman stop` / `podman rm -f` can fail if container PID is stuck — workaround: `podman update --restart=no`, then `kill -9 <pid>`, then `podman rm`
- Port mapping (`-p 8789:8788`) did **not** work for external access — switched to `--network=host`
- Original Dockerfile used `sh -c "uvicorn ..."` which blocked signal handling — fixed to exec form `["uvicorn", ...]`

## GitHub Repo

https://github.com/jackbr4/bookshelf-portal (public)
