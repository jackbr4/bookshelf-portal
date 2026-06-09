# Phase 4 — Frontend Dev Setup

## Context

This is the `bookshelf-portal` project. We are on branch `v2-pipeline`, building a lightweight replacement for Readarr (called Bookshelf). The backend is a FastAPI app; the frontend is React + TypeScript + Vite.

**Phase 4 goal:** Add a release selection step to the UI — between picking a book and confirming a download. The user searches for a book, picks it, sees a list of available releases (epub/pdf, from Prowlarr), picks one, and the download is dispatched.

---

## What exists on the backend (already built and tested)

Three new API endpoints are live on the dev backend (port 8789 on the seedbox):

### `GET /portal/releases?title=...&author=...`
Returns epub/pdf releases for a book from Prowlarr. Auth required (session cookie).

```json
{
  "accepted": [
    {
      "guid": "...",
      "title": "Dune by Frank Herbert [ENG / EPUB]",
      "indexer": "MyAnonamouse",
      "protocol": "torrent",
      "size_mb": 4.8,
      "detected_format": "epub",
      "seeders": 42,
      "age_days": 180,
      "download_url": "http://...",
      "publish_date": "2024-01-15T00:00:00",
      "score": 60,
      "rejected": false,
      "reject_reason": null
    }
  ],
  "rejected": [
    {
      "title": "Dune Audio Collection [ENG / MP3]",
      "rejected": true,
      "reject_reason": "audio format (mp3)",
      ...
    }
  ]
}
```

### `POST /portal/download`
Dispatches a chosen release to rTorrent or SABnzbd. Records it in the history DB.

Request body:
```json
{
  "title": "Dune",
  "author": "Frank Herbert",
  "release_title": "Dune by Frank Herbert [ENG / EPUB]",
  "indexer": "MyAnonamouse",
  "protocol": "torrent",
  "download_url": "http://..."
}
```

Response:
```json
{
  "ok": true,
  "record_id": "uuid",
  "download_id": "TORRENT_HASH_OR_NZO_ID",
  "message": "Sent to rTorrent"
}
```

### `GET /portal/history`
Returns recent downloads (last 50). Auth required.

```json
{
  "items": [
    {
      "id": "uuid",
      "title": "Dune",
      "author": "Frank Herbert",
      "release_title": "Dune by Frank Herbert [ENG / EPUB]",
      "indexer": "MyAnonamouse",
      "protocol": "torrent",
      "status": "downloading",
      "created_at": "2026-05-28T10:00:00+00:00",
      "updated_at": "2026-05-28T10:00:00+00:00",
      "error": null
    }
  ]
}
```

---

## Existing frontend structure

```
frontend/src/
  App.tsx
  components/
    PasswordGate.tsx       — auth screen
    PortalButton.tsx       — styled button component
    PortalInput.tsx        — styled input component
    PortalToast.tsx        — toast notifications
    ResultCard.tsx         — single book result row
    ResultsSection.tsx     — book results list
    SearchPanel.tsx        — search input + submit
    StatusBadge.tsx        — "available" / "in library" badge
  lib/
    api.ts                 — all API calls to backend
    session.ts             — session token management
    types.ts               — TypeScript types
  routes/
    PasswordRoute.tsx      — login page
    RequestRoute.tsx       — main app page (search + request flow)
  styles/
    theme.css
```

The current flow in `RequestRoute.tsx`:

```
idle → searching → results → [user picks book] → requesting → done
```

The `requesting` state calls `POST /portal/request/book` (the old Bookshelf endpoint). We are replacing this with the new two-step flow:

```
idle → searching → results → [user picks book] → loading_releases → selecting_release → downloading → done
```

---

## What needs to be built (Phase 4)

### 1. Update `lib/types.ts`
Add types for the new models:

```ts
export interface ReleaseItem {
  guid: string
  title: string
  indexer: string
  protocol: string
  size_mb: number
  detected_format: string | null
  seeders: number | null
  age_days: number | null
  download_url: string
  publish_date: string | null
  score: number
  rejected: boolean
  reject_reason: string | null
}

export interface ReleasesResponse {
  accepted: ReleaseItem[]
  rejected: ReleaseItem[]
}

export interface DownloadRequest {
  title: string
  author: string
  release_title: string
  indexer: string
  protocol: string
  download_url: string
}

export interface DownloadResponse {
  ok: boolean
  record_id: string
  download_id: string
  message: string
}
```

### 2. Update `lib/api.ts`
Add two new functions:

```ts
export async function getReleases(title: string, author: string): Promise<ReleasesResponse>
export async function dispatchDownload(req: DownloadRequest): Promise<DownloadResponse>
```

### 3. New component: `ReleasesPanel.tsx`
Shows the release list for a selected book. Key requirements:
- Lists `accepted` releases, sorted by score (already sorted by backend)
- Each row shows: format badge (epub highlighted in green, pdf in grey), indexer, size, seeders (for torrents), age
- One "Download" button per row
- Collapsible "Rejected releases" section at the bottom showing filtered-out releases with their reject reason
- Loading state while fetching
- Empty state if no accepted releases found

### 4. Update `RequestRoute.tsx`
Replace the current `requesting` state with the new two-step flow:
- After book selection: fetch `/portal/releases` (show `loading_releases` state)
- Show `ReleasesPanel` with the results (`selecting_release` state)
- On release pick: POST to `/portal/download` → show confirmation (`downloading` → `done`)
- Keep a "Back" affordance so the user can return to book results without re-searching

### 5. Keep the existing `POST /portal/request/book` flow untouched
The old Bookshelf-backed endpoint still works and the existing components (`ResultCard`, `ResultsSection`, `SearchPanel`) do not need to change.

---

## Dev setup

### Prerequisites
- Node.js 18+
- Git

### Steps

**Terminal 1 — SSH tunnel to seedbox backend**
```bash
ssh -N -L 8789:localhost:8789 jackbr4@narvi.whatbox.ca
```
Keep this open. The frontend dev server proxies all `/portal/*` requests through this tunnel to the FastAPI backend running on the seedbox.

**Terminal 2 — seedbox: ensure dev backend is running**
```bash
# SSH into seedbox
ssh jackbr4@narvi.whatbox.ca

# Start dev backend (if not already running)
cd ~/apps/bookshelf-portal/bookshelf-portal/backend
venv/bin/uvicorn app.main:app --port 8789 --env-file ../.env.dev --reload
```

**Terminal 3 — local: pull branch and start frontend**
```bash
git fetch
git checkout v2-pipeline
cd bookshelf-portal/frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Log in with the access code `family`.

**Verify the connection is working:**
```bash
curl -s http://localhost:8789/health
# → {"status":"ok"}
```

---

## Auth for manual API testing

```bash
# Get a session token
TOKEN=$(curl -sf -X POST http://localhost:8789/portal/auth \
  -H "Content-Type: application/json" \
  -d '{"access_code":"family"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['session_token'])")

# Test release search
curl -sf "http://localhost:8789/portal/releases?title=Dune&author=Frank+Herbert" \
  -H "Cookie: session_token=$TOKEN" | python3 -m json.tool | head -40
```

---

## Branch and commit conventions

- Branch: `v2-pipeline`
- Commit format: `Phase 4: <description>`
- Co-author line: `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>`

When Phase 4 is complete, push the branch to GitHub:
```bash
git push origin v2-pipeline
```
The seedbox will then pull it to update the production container.
