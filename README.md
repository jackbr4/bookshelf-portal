# Bookshelf Portal

A self-hosted ebook request and download portal. Search for books via Prowlarr, send them to your torrent or usenet client, and have them automatically imported into Calibre.

## Architecture

```
Browser → Portal → Prowlarr ──► rTorrent
                           │   └► qBittorrent
                           └──► SABnzbd
                                    │
                              watcher (cron)
                                    │
                              calibredb add
                                    │
                            Calibre library
```

The portal serves a React frontend and a FastAPI backend. Users search for books, pick a release from Prowlarr results, and dispatch it to their download client. A cron-based watcher polls for completed downloads and imports them into Calibre automatically.

## Required services

| Service | Purpose |
|---|---|
| [Prowlarr](https://prowlarr.com) | Aggregates search across all configured indexers |
| rTorrent **or** qBittorrent | Handles `.torrent` releases |
| [SABnzbd](https://sabnzbd.org) | Handles `.nzb` (usenet) releases |
| [Calibre](https://calibre-ebook.com) | Ebook library — `calibredb` must be reachable |

Bookshelf / Readarr integration is **optional** — the portal works standalone with Prowlarr for search.

## Quick start (Docker)

```bash
cp backend/.env.example backend/.env
# Edit .env with your values
docker compose up -d
```

Open `http://localhost:8788` and log in with your `APP_PASSWORD`.

## Development

```bash
./start.sh
```

Starts the backend (port 8788) and frontend dev server (port 5173) with hot reload. Default password is `family`. Set `MOCK_MODE=true` to skip live service connections.

## Watcher (cron job)

The watcher polls download clients for completed downloads and imports them into Calibre. Add to crontab:

```cron
* * * * * /path/to/backend/venv/bin/python /path/to/backend/watcher.py >> /var/log/watcher.log 2>&1
```

Pass `--env /path/to/.env` to target a specific env file.

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

### Bookshelf / Readarr (optional)

| Variable | Default | Description |
|---|---|---|
| `BOOKSHELF_ENABLED` | `true` | Set to `false` to use Prowlarr search only |
| `BOOKSHELF_BASE_URL` | `http://localhost:8787` | Readarr/Bookshelf base URL |
| `BOOKSHELF_API_KEY` | `changeme` | API key |

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
      download_client.py   # rTorrent / qBittorrent / SABnzbd dispatch
      prowlarr_client.py   # Prowlarr search + deduplication
      release_filter.py    # Accept/reject/score logic
      history.py           # SQLite download history
      calibre_client.py    # calibredb wrapper
      auth.py              # Session token logic
      models.py            # Pydantic request/response models
      bookshelf_client.py  # Optional Readarr/Bookshelf integration
    watcher.py             # Cron script: poll → import → update history
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
