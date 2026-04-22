# Bookshelf Portal

A self-hosted, password-protected web portal that lets family members search for books and request them to be added to your [Bookshelf](https://github.com/advplyr/bookshelf) (Readarr-compatible) instance. Results are pulled from Bookshelf's own lookup API, enriched by Google Books and Open Library, and annotated with your current library status in real time.

---

## Screenshots

**Login**
<img width="1225" height="874" alt="Login page" src="https://github.com/user-attachments/assets/62efd2c0-6a2f-4281-989b-7e28fef978db" />

**Search**
<img width="1242" height="909" alt="Search page" src="https://github.com/user-attachments/assets/674b341f-e22d-4b7b-be5d-0048bdb5a35c" />

**Results**
<img width="1200" height="900" alt="results page" src="https://github.com/user-attachments/assets/9fc4dd3b-fa59-47e3-b25d-613c23838e73" />

**Book added / already monitored**
<img width="1184" height="878" alt="Book added or already in Bookshelf library" src="https://github.com/user-attachments/assets/69c5aa08-4d53-46d6-bcce-47cafebfb1b6" />

---

## Features

- Password-protected access gate (single shared code, no accounts)
- Searches Bookshelf/Readarr, Google Books, and Open Library in parallel
- Results grouped by language, annotated with library status (Available / Already in Library / Already Monitored)
- One-click book request with status toast feedback
- Fuzzy relevance scoring with junk-result filtering
- Session cookie auth (HTTP-only, HMAC-signed, 8-hour TTL)
- Rate limiting on the auth endpoint (10 req/min)
- Mock mode for local development — no live Bookshelf needed
- Single-container deployment via Docker or Podman

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Browser                                        │
│  React + TypeScript + Bootstrap (Vite)          │
│  PasswordRoute → RequestRoute                   │
│        │  HTTP (cookie auth)                    │
└────────┼────────────────────────────────────────┘
         │
┌────────▼────────────────────────────────────────┐
│  FastAPI (Python 3.12, Uvicorn)                 │
│                                                 │
│  POST /portal/auth      — password + session    │
│  GET  /portal/search    — search pipeline       │
│  POST /portal/request/book   — add a book       │
│  POST /portal/request/series — add a series     │
│  GET  /health           — health check          │
│                                                 │
│  /assets, /{path}       — React SPA (prod)      │
└──────────┬────────────────────────────────────┬─┘
           │                                    │
  ┌────────▼────────┐              ┌────────────▼──────────┐
  │  Bookshelf API  │              │  Google Books API     │
  │  (Readarr fork) │              │  (parallel enrichment)│
  └─────────────────┘              └───────────────────────┘
           │
  ┌────────▼────────┐
  │  Open Library   │
  │  (fallback)     │
  └─────────────────┘
```

### Single-container build

The Dockerfile uses a multi-stage build:

1. **Stage 1 (Node 20)** — `npm run build` compiles the React frontend to `/app/frontend/dist`
2. **Stage 2 (Python 3.12-slim)** — installs Python deps, copies the backend, and copies the built frontend into `/app/static`

At runtime FastAPI serves the React SPA via `StaticFiles` with an SPA fallback for client-side routing. The static directory is only mounted when it exists, so the backend works standalone in development.

### Search pipeline

Each search runs these steps:

1. **Concurrent fetch** — Bookshelf lookup + Google Books API + library fetch run in parallel via `asyncio.gather`
2. **Fallback** — if Bookshelf returns empty or 5xx, Open Library is tried
3. **Query fallbacks** — on Bookshelf 5xx, the query is retried with apostrophes stripped, leading articles removed, and/or shortened to the first two words
4. **Normalise** — titles are NFKC-normalised, edition noise stripped, punctuation collapsed
5. **Score** — fuzzy matching (rapidfuzz `token_sort_ratio`) against both title and author tokens, with bonuses for exact matches and penalties for junk phrases (summaries, study guides, etc.)
6. **Filter** — results below a minimum score threshold are separated into a "filtered" pool
7. **Deduplicate** — editions of the same book collapse to the highest-scoring row; native Bookshelf IDs win tiebreaks over Google Books / Open Library IDs
8. **Language enrichment** — results without a language tag get one inferred from Google Books metadata or Polish diacritics heuristic
9. **Library annotation** — results matched against the live library are marked as Already in Library or Already Monitored
10. **Return** — top 20 results returned to the frontend, grouped by language

### Authentication

- User submits the shared access code → backend validates against `APP_PASSWORD`
- On success, an HMAC-signed session token (via `itsdangerous`) is set as an HTTP-only `SameSite=Lax` cookie
- All protected endpoints validate the cookie via a FastAPI `Depends` guard
- Sessions expire after `SESSION_TTL_HOURS` (default 8 hours)

### Book add flow

Adding a book is more complex than it looks due to Readarr's author-centric data model:

1. The book's full lookup payload is fetched from Bookshelf by `foreignBookId` (or by title for Google Books / Open Library results)
2. The author's `foreignAuthorId` is resolved via `/api/v1/author/lookup`
3. The add payload sets the **author as unmonitored** (`"monitored": false`) so Bookshelf catalogs their back-catalog without immediately downloading everything
4. The specific requested book is set to **monitored** with `searchForNewBook: true`
5. A background task polls until the author's catalog is populated, then ensures the target book stays monitored and unmonitors any other books that were accidentally marked monitored during catalog import

---

## Requirements

| Requirement | Version |
|---|---|
| Python | 3.12+ |
| Node.js | 20+ |
| npm | 10+ |
| Docker **or** Podman | Any recent version |

A running [Bookshelf](https://github.com/advplyr/bookshelf) (or Readarr) instance is required in production. In development, `MOCK_MODE=true` (the default) bypasses this entirely.

---

## Local Development

The quickest way to get started:

```bash
cd bookshelf-portal
./start.sh
```

This will:
- Create a Python venv and install backend dependencies
- Install frontend npm dependencies
- Start the backend on `http://localhost:8788` with hot-reload
- Start the frontend dev server on `http://localhost:5173`

Open `http://localhost:5173` and log in with password `family`.

Mock mode is on by default — no Bookshelf instance needed.

### Manual setup

**Backend**

```bash
cd bookshelf-portal/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp ../.env.example .env   # edit as needed
.venv/bin/uvicorn app.main:app --reload --port 8788
```

**Frontend**

```bash
cd bookshelf-portal/frontend
npm install
npm run dev
```

**Tests**

```bash
cd bookshelf-portal/frontend
npm test
```

---

## Configuration

All configuration is via environment variables (or a `.env` file in `bookshelf-portal/`).

Copy `.env.example` to `.env` and fill in values:

```bash
cp bookshelf-portal/.env.example bookshelf-portal/.env
```

| Variable | Default | Required in prod | Description |
|---|---|---|---|
| `BOOKSHELF_BASE_URL` | `http://localhost:8787` | Yes | Base URL of your Bookshelf/Readarr instance |
| `BOOKSHELF_API_KEY` | `changeme` | Yes | API key from Bookshelf → Settings → General |
| `APP_PASSWORD` | `family` | Yes | Shared access code shown to users |
| `APP_SESSION_SECRET` | `changeme-secret` | Yes | Random secret for HMAC session signing — generate with `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `MOCK_MODE` | `true` | — | Set to `false` to use live Bookshelf |
| `PORT` | `8788` | — | Port the backend listens on |
| `SESSION_TTL_HOURS` | `8` | — | Session cookie lifetime in hours |
| `GOOGLE_BOOKS_API_KEY` | _(unset)_ | — | Optional Google Books API key — without it you get 1000 unauthenticated requests/day |

---

## Docker Deployment

```bash
cd bookshelf-portal
cp .env.example .env   # set MOCK_MODE=false and fill in real values

# Docker Compose
docker compose up -d

# Or plain Docker
docker build -t bookshelf-portal .
docker run -d --name bookshelf-portal -p 8788:8788 --env-file .env bookshelf-portal
```

Health check: `curl http://localhost:8788/health`

---

## Podman Deployment (rootless, host networking)

If your host's container networking doesn't forward ports to external interfaces (common on seedboxes with rootless Podman), use `--network=host`:

```bash
podman build -t bookshelf-portal ./bookshelf-portal
podman run -d \
  --name bookshelf-portal \
  --restart=always \
  --network=host \
  --env-file /path/to/.env \
  bookshelf-portal
```

> **Why `--network=host`?** Podman's slirp4netns (`-p host:container`) doesn't propagate to external interfaces on some hosts. Host networking bypasses this entirely.

---

## CI/CD (GitHub Actions)

Pushing to `main` triggers an automated deploy via SSH:

1. SSH into the seedbox
2. `git pull origin main`
3. `podman build` the new image
4. Replace the running container with `podman run --replace`
5. Health check via `curl /health`

### Setup

1. Generate an SSH key pair: `ssh-keygen -t ed25519 -C "github-actions"`
2. Add the public key to `~/.ssh/authorized_keys` on your server
3. Add the private key as a GitHub Actions secret named `SEEDBOX_SSH_KEY` (repo → Settings → Secrets → Actions)
4. Update `.github/workflows/deploy.yml` with your server hostname and username if needed

---

## Project Structure

```
bookshelf-portal/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app — routes, middleware, SPA serving
│   │   ├── settings.py           # Pydantic-settings env config
│   │   ├── auth.py               # Session token creation and validation
│   │   ├── models.py             # Pydantic request/response models
│   │   ├── bookshelf_client.py   # Bookshelf/Readarr API client + mock mode
│   │   └── search_adapter.py     # Search pipeline: normalise, score, dedup, rank
│   ├── requirements.txt
│   └── .env                      # Local dev config (not committed)
├── frontend/
│   ├── src/
│   │   ├── components/           # Reusable UI components (SearchPanel, ResultCard, etc.)
│   │   ├── routes/               # Page-level routes (PasswordRoute, RequestRoute)
│   │   ├── lib/                  # API client, session helpers, shared types
│   │   ├── mocks/                # Mock API for dev and testing
│   │   └── styles/               # CSS theme variables
│   ├── vite.config.ts
│   └── package.json
├── Dockerfile                    # Multi-stage build (Node → Python)
├── docker-compose.yml
├── start.sh                      # Dev convenience script
└── .env.example                  # Environment variable template
```

---

## Known Limitations

- **Author over-monitoring**: Readarr's data model requires adding an author to add a book. The portal adds authors as unmonitored and patches this with a background task, but edge cases can occasionally result in extra books being picked up for an author.
- **Series search**: The series add endpoint exists but series are not currently surfaced in search results — series metadata from Bookshelf's lookup API is inconsistent.
- **Rate limiting**: Only the auth endpoint is rate-limited. Search and add endpoints rely on session authentication as a throttle.

---

## Adapting for Readarr

This portal targets Bookshelf (a Readarr fork) but the API is largely compatible with vanilla Readarr. To use with Readarr:

- Point `BOOKSHELF_BASE_URL` at your Readarr instance
- The `/api/v1/book/lookup`, `/api/v1/book`, `/api/v1/author/lookup`, and `/api/v1/rootfolder` endpoints are standard Readarr v1 API — no changes needed
- Root folder and quality/metadata profile resolution uses whatever Readarr has configured as defaults
