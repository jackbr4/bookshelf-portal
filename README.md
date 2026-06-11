# Bookshelf Portal

A self-hosted ebook and audiobook request portal. Search for books via Prowlarr, send them to your torrent or usenet client, and have them automatically imported into Calibre (ebooks) or Audiobookshelf (audiobooks).

## Architecture

```
Browser → Portal → Prowlarr ──► rTorrent
                           │   └► qBittorrent
                           └──► SABnzbd
                                    │
                              watcher (cron)
                              ┌─────┴─────┐
                         ebook?        audiobook?
                              │              │
                        calibredb add    copy to
                              │         AUDIOBOOKS_DIR
                        Calibre lib   Audiobookshelf
```

The portal serves a server-rendered frontend and a FastAPI backend. Users search for books, pick a release from Prowlarr results (ebook or audiobook tab), and dispatch it to their download client. A cron-based watcher polls for completed downloads and routes them: ebooks are imported into Calibre via `calibredb add`; audiobooks are copied into the Audiobookshelf library directory.

## Required services

| Service | Purpose |
|---|---|
| [Prowlarr](https://prowlarr.com) | Aggregates search across all configured indexers |
| rTorrent **or** qBittorrent | Handles `.torrent` releases |
| [SABnzbd](https://sabnzbd.org) | Handles `.nzb` (usenet) releases |
| [Calibre](https://calibre-ebook.com) | Ebook library — `calibredb` must be reachable |
| [Audiobookshelf](https://www.audiobookshelf.org) | Audiobook library — the watcher copies completed audiobooks here |

Bookshelf / Readarr integration is **optional** — the portal works standalone with Prowlarr for search.

## Quick start (Docker)

```bash
cp backend/.env.example backend/.env
# Edit .env with your values
docker compose up -d
```

Open `http://localhost:8788/portal` and log in with your `APP_PASSWORD`.

## Development

```bash
./start.sh
```

Starts the backend (port 8788) and frontend dev server (port 5173) with hot reload. Default password is `family`. Set `MOCK_MODE=true` to skip live service connections.

## Goodreads shelf sync

`backend/goodreads_sync.py` is an optional cron script that automatically discovers books from Goodreads "to-read" shelves and dispatches downloads for any that aren't already in your Calibre library.

### How it works

1. Fetches all books from each configured Goodreads profile's public RSS shelf feed.
2. Skips books already in Calibre (fuzzy title + author matching handles subtitles, series markers, and Calibre's reversed author storage format).
3. Searches Prowlarr for each missing book, prefers epub, and dispatches the best result.
4. Before dispatching, checks the number of active (seeding < 72 h) torrents in rTorrent against `MAM_MAX_UNSATISFIED` to avoid hitting MyAnonamouse's 150-torrent limit.
5. Books with no Prowlarr result are retried after 14 days.

### Multi-user profiles

Family members can add their own Goodreads profiles directly through the portal. Go to **Admin → Goodreads Profiles** and paste in a Goodreads user ID (the `12345678-firstname` portion of the profile URL). Each profile can use a different shelf name (default: `to-read`).

**Backlog control:** by default, only books added to the shelf *after* the profile is created are synced ("new additions only"). Checking **"Download all books from my Want to Read shelf"** when adding a profile enables full-backlog mode — the entire shelf is eligible for download, worked through gradually across successive cron runs subject to the MAM slot cap. A note in the UI warns that a large shelf may take a few days to fully import.

Each profile card in the Admin UI shows its sync mode: **Full shelf** or **New additions from YYYY-MM-DD**, so it's always clear how a profile is configured.

Deduplication is global — a book already queued or in Calibre won't be downloaded twice regardless of which profile requested it.

Profiles are managed in the `goodreads_profiles` table of the history database. The first profile is auto-migrated from `GOODREADS_USER_ID` in `.env` on the initial run.

### Cron setup

```cron
0 */4 * * * /path/to/backend/venv/bin/python /path/to/backend/goodreads_sync.py \
    --env /path/to/.env >> ~/logs/goodreads_sync.log 2>&1
```

Runs every 4 hours. Pass `--dry-run` to preview what would be dispatched without actually downloading anything. Pass `--max N` to override the per-run dispatch limit for one run.

## Watcher (cron job)

The watcher polls download clients for completed downloads and imports them automatically. Add to crontab:

```cron
* * * * * /path/to/backend/venv/bin/python /path/to/backend/watcher.py >> /var/log/watcher.log 2>&1
```

Pass `--env /path/to/.env` to target a specific env file.

**Routing logic:**
- **Ebook** (`media_type=ebook`) — runs `calibredb add` to import the file into Calibre, then relabels the torrent to the imported category.
- **Audiobook** (`media_type=audiobook`) — copies the completed download (single file or directory) into `AUDIOBOOKS_DIR/Author - Title/`. Files are copied, not moved, so seeding continues. Audiobookshelf picks up the new folder on its next library scan.

## Configuration

Copy `backend/.env.example` to `backend/.env` and fill in your values.

### App

| Variable | Default | Description |
|---|---|---|
| `APP_PASSWORD` | `family` | Shared access code for the portal |
| `APP_SESSION_SECRET` | `changeme-secret` | Secret for signing session cookies — use a long random string in production |
| `SESSION_TTL_HOURS` | `8.0` | Session lifetime in hours |
| `MOCK_MODE` | `true` | Set to `false` to use live services |
| `PORT` | `8788` | Backend listen port |

### Prowlarr

| Variable | Default | Description |
|---|---|---|
| `PROWLARR_BASE_URL` | `http://localhost:29254` | Prowlarr base URL |
| `PROWLARR_API_KEY` | `changeme` | API key (Settings → General) |

### Torrent client

Set `TORRENT_CLIENT=rtorrent` (default) or `TORRENT_CLIENT=qbittorrent`.

**rTorrent**

| Variable | Default | Description |
|---|---|---|
| `RTORRENT_URL` | `https://localhost:443/xmlrpc` | XMLRPC endpoint |
| `RTORRENT_USER` | *(empty)* | HTTP basic auth username |
| `RTORRENT_PASSWORD` | *(empty)* | HTTP basic auth password |
| `RTORRENT_DOWNLOAD_DIR` | `/downloads` | Save directory |
| `RTORRENT_CATEGORY` | `books` | Label applied on dispatch |
| `RTORRENT_IMPORTED_CATEGORY` | `books-imported` | Label applied after Calibre import |

**qBittorrent**

| Variable | Default | Description |
|---|---|---|
| `QBITTORRENT_URL` | `http://localhost:8080` | Web UI base URL |
| `QBITTORRENT_USER` | `admin` | Web UI username |
| `QBITTORRENT_PASSWORD` | `adminadmin` | Web UI password |
| `QBITTORRENT_DOWNLOAD_DIR` | `/downloads` | Save path for new torrents |
| `QBITTORRENT_CATEGORY` | `books` | Category applied on dispatch |
| `QBITTORRENT_IMPORTED_CATEGORY` | `books-imported` | Category applied after Calibre import |

### SABnzbd

| Variable | Default | Description |
|---|---|---|
| `SABNZBD_BASE_URL` | `http://localhost:8080` | SABnzbd base URL |
| `SABNZBD_API_KEY` | `changeme` | API key |
| `SABNZBD_CATEGORY` | `books` | Category for new downloads |

### Calibre

| Variable | Default | Description |
|---|---|---|
| `CALIBRE_LIBRARY_PATH` | `/calibre/library` | Path to your Calibre library directory |
| `CALIBRE_IMAGE` | `lscr.io/linuxserver/calibre:latest` | Docker image used to run `calibredb` when not installed locally |
| `CALIBREDB_BOOKS_DIR` | `/books` | Source directory scanned by `calibredb add` |

### Audiobookshelf

| Variable | Default | Description |
|---|---|---|
| `AUDIOBOOKS_DIR` | `/audiobooks` | Path to your Audiobookshelf library directory. Completed audiobooks are copied here as `Author - Title/`. |

### Bookshelf / Readarr (optional)

| Variable | Default | Description |
|---|---|---|
| `BOOKSHELF_ENABLED` | `true` | Set to `false` to use Prowlarr search only |
| `BOOKSHELF_BASE_URL` | `http://localhost:8787` | Readarr/Bookshelf base URL |
| `BOOKSHELF_API_KEY` | `changeme` | API key |

### Goodreads shelf sync

| Variable | Default | Description |
|---|---|---|
| `GOODREADS_USER_ID` | *(empty)* | Your Goodreads user ID (e.g. `12345678-firstname`). Auto-migrated to the database as the first profile on initial run. |
| `GOODREADS_SHELF` | `to-read` | Shelf name to sync for the initial profile |
| `GOODREADS_MAX_PER_RUN` | `3` | Maximum dispatches per cron run (MAM slot check is the hard cap) |
| `MAM_MAX_UNSATISFIED` | `150` | Maximum allowed unsatisfied (seeding < 72 h) MAM torrents before the run is capped to zero |

### Release filter tuning

These control which releases are accepted and how they are ranked. Adjust to match your indexer setup.

| Variable | Default | Description |
|---|---|---|
| `FILTER_TRUSTED_INDEXERS` | `myanon,mam` | Comma-separated substrings matched against indexer names (case-insensitive). Matching indexers skip the 512 KB minimum-size check — useful for curated trackers where short books are legitimate. |
| `FILTER_PREFERRED_INDEXERS` | `myanon,mam` | Comma-separated substrings. Matching indexers receive a score bonus, pushing their results toward the top. |

### History

| Variable | Default | Description |
|---|---|---|
| `HISTORY_DB_PATH` | `./history.db` | Path to the SQLite download history database |

## Project structure

```
bookshelf-portal/
  backend/
    app/
      main.py              # FastAPI routes
      settings.py          # All configuration (pydantic-settings)
      test_page.py         # Main portal HTML (served at /portal)
      admin_page.py        # Admin page HTML — History + Goodreads Profiles tabs
      download_client.py   # rTorrent / qBittorrent / SABnzbd dispatch
      prowlarr_client.py   # Prowlarr search + release filtering
      release_filter.py    # Accept/reject/score logic for ebooks and audiobooks
      history.py           # SQLite download history + Goodreads profile store
      calibre_library.py   # Calibre metadata.db reader (library presence checks)
      auth.py              # Session token logic
      models.py            # Pydantic request/response models
      bookshelf_client.py  # Optional Readarr/Bookshelf integration
    goodreads_sync.py      # Cron script: Goodreads shelf → Prowlarr → download client
    watcher.py             # Cron script: poll downloads → import to Calibre or Audiobookshelf
    cleanup.py             # Cron script: remove old imported torrents from rTorrent
    requirements.txt
    .env.example
  frontend/
    src/
      components/          # React UI components
      routes/              # Page routes
      lib/                 # API client, types
    vite.config.ts
    package.json
  Dockerfile
  docker-compose.yml
  start.sh
```
