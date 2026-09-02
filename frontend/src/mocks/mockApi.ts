import type {
  ReleasesResponse,
  AuthResponse,
  DownloadResponse,
  HistoryItem,
  SeedingItem,
  GoodreadsProfile,
  ReleaseItem,
  MediaType,
  MamStatus,
  ImportExtractResponse,
  ImportResolveStatus,
  ImportResolveItem,
  BookCandidate,
} from '../lib/types';

const MOCK_PASSWORD = 'family';
// Mirrors the backend's MOCK_MAM_EXHAUSTED: report 150/150 with a ~2h14m
// countdown so the red banner can be exercised without a real rTorrent.
const MOCK_MAM_EXHAUSTED = import.meta.env.VITE_MOCK_MAM_EXHAUSTED === 'true';
const MAM_LIMIT = 150;
const MAM_BLOCK_THRESHOLD = 145;

const MOCK_EBOOK_RELEASES: ReleaseItem[] = [
  {
    guid: 'eb1',
    title: 'NIV Holy Bible: New International Version by Zondervan [ENG / EPUB]',
    indexer: 'MyAnonamouse',
    protocol: 'torrent',
    sizeMb: 10.7,
    detectedFormat: 'EPUB',
    seeders: 88,
    ageDays: 845,
    downloadUrl: 'https://example.com/eb1',
    score: 69,
  },
  {
    guid: 'eb2',
    title: 'The Holy Bible: King James version by American Bible Society [ENG / EPUB]',
    indexer: 'MyAnonamouse',
    protocol: 'torrent',
    sizeMb: 1.4,
    detectedFormat: 'EPUB',
    seeders: 242,
    ageDays: 5043,
    downloadUrl: 'https://example.com/eb2',
    score: 65,
  },
  {
    guid: 'eb3',
    title: 'Holy Bible: New International Version, NIV, Open Bible by Thomas Nelson Inc [ENG / EPUB]',
    indexer: 'MyAnonamouse',
    protocol: 'torrent',
    sizeMb: 18.3,
    detectedFormat: 'EPUB',
    seeders: 34,
    ageDays: 844,
    downloadUrl: 'https://example.com/eb3',
    score: 62,
  },
];

const MOCK_AUDIO_RELEASES: ReleaseItem[] = [
  {
    guid: 'ab1',
    title: 'The Holy Bible in Audio - King James Version by Christianaudio com [ENG / M4B]',
    indexer: 'MyAnonamouse',
    protocol: 'torrent',
    sizeMb: 1954.6,
    detectedFormat: 'M4B',
    seeders: 19,
    ageDays: 2231,
    downloadUrl: 'https://example.com/ab1',
    score: 58,
  },
  {
    guid: 'ab2',
    title: 'The Holy Bible: King James Version by King James Bible [ENG / MP3]',
    indexer: 'MyAnonamouse',
    protocol: 'torrent',
    sizeMb: 1228.8,
    detectedFormat: 'MP3',
    seeders: 51,
    ageDays: 396,
    downloadUrl: 'https://example.com/ab2',
    score: 55,
  },
];

const MOCK_HISTORY: HistoryItem[] = [
  {
    id: 'h1',
    title: 'Moby Dick',
    author: 'Herman Melville',
    releaseTitle: 'Moby Dick by Herman Melville [ENG / M4B]',
    indexer: 'MyAnonamouse',
    protocol: 'torrent',
    mediaType: 'audiobook',
    status: 'imported',
    downloadId: 'ABC123',
    createdAt: '2026-06-11T10:30:00Z',
    updatedAt: '2026-06-11T11:00:00Z',
  },
  {
    id: 'h2',
    title: 'the right stuff',
    author: 'Tom Wolfe',
    releaseTitle: 'The Right Stuff by Tom Wolfe [ENG / EPUB]',
    indexer: 'MyAnonamouse',
    protocol: 'torrent',
    mediaType: 'ebook',
    status: 'imported',
    downloadId: 'DEF456',
    createdAt: '2026-06-11T04:52:00Z',
    updatedAt: '2026-06-11T05:30:00Z',
  },
  {
    id: 'h3',
    title: 'Same bed different dreams',
    author: 'Ed Park',
    releaseTitle: 'Ed Park - Same Bed Different Dreams (epub)',
    indexer: 'NZBgeek',
    protocol: 'usenet',
    source: 'SABnzbd',
    mediaType: 'ebook',
    status: 'error',
    error: 'SABnzbd: Aborted, cannot be completed - missing articles',
    createdAt: '2026-06-04T09:25:00Z',
    updatedAt: '2026-06-04T10:00:00Z',
  },
];

let mockProfiles: GoodreadsProfile[] = [
  {
    id: 'p1',
    name: 'Brendan',
    user_id: '1398435-brendan',
    shelf: 'to-read',
    sync_from: null,
    active: 1,
    created_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'p2',
    name: 'Ewa',
    user_id: '96370075-ewa-jackson',
    shelf: 'to-read',
    sync_from: '2026-06-09',
    active: 1,
    created_at: '2026-06-09T00:00:00Z',
  },
];

function delay(ms = 600): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

export async function mockAuth(accessCode: string): Promise<AuthResponse> {
  await delay(400);
  if (accessCode === MOCK_PASSWORD) {
    return {
      ok: true,
      sessionToken: 'mock-token',
      expiresAt: new Date(Date.now() + 8 * 3600 * 1000).toISOString(),
    };
  }
  return { ok: false };
}

export async function mockGetReleases(title: string, author: string): Promise<ReleasesResponse> {
  await delay(900);
  const q = `${title} ${author}`.toLowerCase();
  const isBible = q.includes('bible') || q.includes('holy');
  // "dune" simulates a book that was requested before: the top release is
  // flagged and a history banner appears.
  const isRequested = q.includes('dune');
  return {
    ebookAccepted: isBible
      ? MOCK_EBOOK_RELEASES
      : [{ ...MOCK_EBOOK_RELEASES[0], alreadyRequested: isRequested }],
    ebookRejected: isBible ? [{ ...MOCK_EBOOK_RELEASES[0], guid: 'rej1', rejected: true, rejectReason: 'Too small' }] : [],
    audiobookAccepted: isBible ? MOCK_AUDIO_RELEASES : [],
    audiobookRejected: isBible ? [] : [],
    calibreTitle: null,
    audiobooksTitle: null,
    historyMatch: isRequested
      ? {
          status: 'imported',
          createdAt: new Date(Date.now() - 12 * 24 * 3600 * 1000).toISOString(),
          releaseTitle: MOCK_EBOOK_RELEASES[0].title,
          mediaType: 'ebook',
          protocol: 'torrent',
        }
      : null,
  };
}

export async function mockDownload(_args: {
  title: string;
  author: string;
  releaseTitle: string;
  indexer: string;
  protocol: string;
  downloadUrl: string;
  mediaType: MediaType;
}): Promise<DownloadResponse> {
  await delay(500);
  return {
    ok: true,
    recordId: 'mock-record',
    downloadId: 'MOCKHASH',
    message: 'Sent to download client',
  };
}

export async function mockGetHistory(): Promise<HistoryItem[]> {
  await delay(400);
  return MOCK_HISTORY;
}

export async function mockGetSeeding(): Promise<SeedingItem[]> {
  await delay(200);
  return [
    { hash: 'ABC123', finishedAt: Math.floor(Date.now() / 1000) - 3600 },
    { hash: 'DEF456', finishedAt: Math.floor(Date.now() / 1000) - 7200 },
  ];
}

export async function mockGetGoodreadsProfiles(): Promise<GoodreadsProfile[]> {
  await delay(300);
  return [...mockProfiles];
}

export async function mockAddGoodreadsProfile(body: {
  name: string;
  user_id: string;
  shelf: string;
  sync_from?: string | null;
}): Promise<void> {
  await delay(300);
  mockProfiles = [
    ...mockProfiles,
    {
      id: `p${mockProfiles.length + 1}`,
      name: body.name,
      user_id: body.user_id,
      shelf: body.shelf,
      sync_from: body.sync_from ?? null,
      active: 1,
      created_at: new Date().toISOString(),
    },
  ];
}

export async function mockDeleteGoodreadsProfile(profileId: string): Promise<void> {
  await delay(200);
  mockProfiles = mockProfiles.filter(p => p.id !== profileId);
}

export async function mockGetMamStatus(): Promise<MamStatus> {
  await delay(200);
  const now = Math.floor(Date.now() / 1000);
  const unsatisfied = MOCK_MAM_EXHAUSTED ? MAM_LIMIT : 143;
  return {
    unsatisfied,
    limit: MAM_LIMIT,
    blockThreshold: MAM_BLOCK_THRESHOLD,
    slotsFree: Math.max(0, MAM_BLOCK_THRESHOLD - unsatisfied),
    blocked: unsatisfied >= MAM_BLOCK_THRESHOLD,
    nextFreeAt: MOCK_MAM_EXHAUSTED ? now + 2 * 3600 + 14 * 60 : now + 5 * 3600,
    serverTime: now,
  };
}

// --- List import ---

// Same canned list as the backend mock; titles chosen so the fake resolve
// below shows every status.
const MOCK_CANDIDATES: BookCandidate[] = [
  { title: 'The Left Hand of Darkness', author: 'Ursula K. Le Guin', confidence: 'high' },
  { title: 'Piranesi', author: 'Susanna Clarke', confidence: 'high' },
  { title: 'Weather', author: 'Jenny Offill', confidence: 'high' },
  { title: 'Stoner', author: '', confidence: 'low' },
  { title: 'A Visit from the Goon Squad', author: 'Jennifer Egan', confidence: 'low' },
  { title: 'Lincoln in the Bardo', author: 'George Saunders', confidence: 'high' },
  { title: 'Bewilderment', author: 'Richard Powers', confidence: 'high' },
  { title: 'Trust', author: 'Hernan Diaz', confidence: 'high' },
];

export async function mockExtractList(input: { url: string } | { text: string }): Promise<ImportExtractResponse> {
  await delay(900);
  if ('url' in input) {
    return { books: [...MOCK_CANDIDATES], source: 'url', sourceTitle: 'Mock: 7 novels worth your time' };
  }
  return { books: [...MOCK_CANDIDATES], source: 'text', sourceTitle: null };
}

interface MockJob {
  results: ImportResolveItem[];
  startedAt: number;
  includeAudiobooks?: boolean;
}

const mockJobs = new Map<string, MockJob>();

function mockRelease(guid: string, title: string, fmt: string, sizeMb: number, score: number, protocol = 'torrent'): ReleaseItem {
  return {
    guid,
    title,
    indexer: protocol === 'torrent' ? 'MyAnonamouse' : 'NZBgeek',
    protocol,
    sizeMb,
    detectedFormat: fmt,
    seeders: protocol === 'torrent' ? 42 : null,
    ageDays: 120,
    downloadUrl: `http://localhost:29254/${guid}`,
    score,
  };
}

/** Mirrors backend import_jobs._mock_resolve so both mock layers agree. */
function mockResolveOne(item: ImportResolveItem): ImportResolveItem {
  const h = Array.from(item.title.toLowerCase()).reduce((a, c) => a + c.charCodeAt(0), 0);
  if (h % 10 === 3) return { ...item, status: 'error', error: 'Prowlarr search timed out (mock)' };
  const empty: ReleasesResponse = { ebookAccepted: [], ebookRejected: [], audiobookAccepted: [], audiobookRejected: [] };
  if (h % 5 === 0) return { ...item, status: 'not_found', releases: empty };
  if (h % 4 === 0) return { ...item, status: 'in_library', releases: { ...empty, calibreTitle: item.title } };
  const label = item.author ? `${item.title} by ${item.author}` : item.title;
  const requested = h % 7 === 1;
  const ebooks = [
    { ...mockRelease(`${h}-eb1`, `${label} [ENG / EPUB]`, 'EPUB', 1.8, 72), alreadyRequested: requested },
    mockRelease(`${h}-eb2`, `${label} [ENG / MOBI]`, 'MOBI', 2.1, 60),
    mockRelease(`${h}-eb3`, `${label} (epub)`, 'EPUB', 1.6, 55, 'usenet'),
  ];
  return {
    ...item,
    status: requested ? 'requested' : 'available',
    releases: {
      ...empty,
      ebookAccepted: ebooks,
      audiobookAccepted: h % 2 === 0 ? [mockRelease(`${h}-ab1`, `${label} [ENG / M4B]`, 'M4B', 480.2, 64)] : [],
      historyMatch: requested
        ? {
            status: 'downloading',
            createdAt: new Date(Date.now() - 3 * 24 * 3600 * 1000).toISOString(),
            releaseTitle: ebooks[0].title,
            mediaType: 'ebook',
            protocol: 'torrent',
          }
        : null,
    },
  };
}

export async function mockStartResolve(books: { title: string; author: string }[], includeAudiobooks = true): Promise<{ jobId: string; total: number }> {
  await delay(200);
  const jobId = `mock-${Date.now()}`;
  mockJobs.set(jobId, {
    startedAt: Date.now(),
    includeAudiobooks,
    results: books.map((b, i) => ({ index: i, title: b.title, author: b.author, status: 'pending' })),
  });
  return { jobId, total: books.length };
}

export async function mockGetResolveStatus(jobId: string): Promise<ImportResolveStatus> {
  await delay(100);
  const job = mockJobs.get(jobId);
  if (!job) throw new Error('Unknown or expired resolve job');
  // Resolve ~one book per 700ms, three at a time, like the real semaphore.
  const elapsed = Date.now() - job.startedAt;
  const resolvedCount = Math.min(job.results.length, Math.floor(elapsed / 700) * 3);
  const results = job.results.map((r, i) => {
    if (i >= resolvedCount || r.status !== 'pending') return r;
    const resolved = mockResolveOne(r);
    if (job.includeAudiobooks === false && resolved.releases) {
      resolved.releases = { ...resolved.releases, audiobookAccepted: [], audiobookRejected: [] };
    }
    return resolved;
  });
  job.results = results;
  const completed = results.filter(r => r.status !== 'pending').length;
  return { jobId, done: completed === results.length, total: results.length, completed, results };
}

export async function mockCancelResolve(jobId: string): Promise<void> {
  mockJobs.delete(jobId);
}
