# Bookshelf Request Portal

A self-hosted web portal that lets family members search for books and series and request them to be added to your Bookshelf (Readarr-compatible) instance.

## Features

- Password-protected access gate
- Search for books and series
- One-click request to add to Bookshelf
- Status badges: Available / Already in Library / Already Monitored
- Mock mode for development (no live Bookshelf needed)
- Session cookie authentication (8-hour TTL)
- Rate limiting on auth endpoint

## Quick Start (Development)

```bash
cd bookshelf-portal
./start.sh
```

Then open http://localhost:5173 and enter password `family`.

The script automatically:
- Creates a Python venv and installs backend deps
- Installs frontend npm deps
- Starts both servers with hot-reload

## Manual Setup

### Backend

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # edit as needed
.venv/bin/uvicorn app.main:app --reload --port 8788
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Tests

```bash
cd frontend
npm test
```

## Configuration

Copy `backend/.env` and set:

| Variable | Default | Description |
|---|---|---|
| `BOOKSHELF_BASE_URL` | `http://localhost:8787` | Readarr/Bookshelf base URL |
| `BOOKSHELF_API_KEY` | `changeme` | API key from Bookshelf settings |
| `APP_PASSWORD` | `family` | Shared access code for the portal |
| `APP_SESSION_SECRET` | `dev-secret-change-in-prod` | Secret for signing session tokens |
| `MOCK_MODE` | `true` | Use mock data instead of live Bookshelf |
| `PORT` | `8788` | Backend port |

## Docker

```bash
cp .env.example .env  # fill in real values, set MOCK_MODE=false
docker compose up -d
```

## Project Structure

```
bookshelf-portal/
  backend/
    app/
      main.py           # FastAPI app, routes
      settings.py       # Pydantic settings
      auth.py           # Session token logic
      models.py         # Pydantic models
      bookshelf_client.py  # Readarr API client + mock
    requirements.txt
    .env
  frontend/
    src/
      components/       # React UI components
      routes/           # Page-level route components
      lib/              # API client, session, types
      mocks/            # Mock API for dev/test
      styles/           # CSS theme
    vite.config.ts
    package.json
  Dockerfile
  docker-compose.yml
  start.sh
```
