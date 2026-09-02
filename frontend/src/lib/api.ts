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
  ExtractErrorCode,
} from './types';
import {
  mockAuth,
  mockGetReleases,
  mockDownload,
  mockGetHistory,
  mockGetSeeding,
  mockGetGoodreadsProfiles,
  mockAddGoodreadsProfile,
  mockDeleteGoodreadsProfile,
  mockGetMamStatus,
  mockExtractList,
  mockStartResolve,
  mockGetResolveStatus,
  mockCancelResolve,
} from '../mocks/mockApi';

const MOCK_MODE = import.meta.env.VITE_MOCK_MODE === 'true';

/**
 * Non-2xx API response. `detail` keeps the structured payload some endpoints
 * return (e.g. the MAM 429 carries `next_free_at`); `message` is always a
 * human-readable string.
 */
export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, message: string, detail: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.status === 401) {
    throw new Error('SESSION_EXPIRED');
  }
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    let message = `HTTP ${res.status}`;
    let detail: unknown = text;
    try {
      const json = JSON.parse(text);
      detail = json.detail ?? json;
      const d = json.detail;
      if (typeof d === 'string') message = d;
      else if (d && typeof d.message === 'string') message = d.message;
      else if (typeof json.message === 'string') message = json.message;
      else if (text) message = text;
    } catch {
      if (text) message = text;
    }
    throw new ApiError(res.status, message, detail);
  }
  return res.json() as Promise<T>;
}

/** Extract the MAM 429 payload from a download error, if that's what it is. */
export function mamBlockedDetail(err: unknown): { nextFreeAt: number | null } | null {
  if (!(err instanceof ApiError) || err.status !== 429) return null;
  const d = err.detail as { next_free_at?: number | null } | null;
  if (!d || typeof d !== 'object' || !('next_free_at' in d)) return null;
  return { nextFreeAt: d.next_free_at ?? null };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function mapRelease(r: any): ReleaseItem {
  return {
    guid: r.guid,
    title: r.title,
    indexer: r.indexer,
    protocol: r.protocol,
    sizeMb: r.size_mb,
    detectedFormat: r.detected_format,
    seeders: r.seeders,
    ageDays: r.age_days,
    downloadUrl: r.download_url,
    publishDate: r.publish_date,
    score: r.score ?? 0,
    rejected: r.rejected,
    rejectReason: r.reject_reason,
    alreadyRequested: !!r.already_requested,
  };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function mapReleases(data: any): ReleasesResponse {
  return {
    ebookAccepted: (data.ebook_accepted ?? []).map(mapRelease),
    ebookRejected: (data.ebook_rejected ?? []).map(mapRelease),
    audiobookAccepted: (data.audiobook_accepted ?? []).map(mapRelease),
    audiobookRejected: (data.audiobook_rejected ?? []).map(mapRelease),
    calibreTitle: data.calibre_title,
    audiobooksTitle: data.audiobooks_title,
    historyMatch: data.history_match
      ? {
          status: data.history_match.status,
          createdAt: data.history_match.created_at,
          releaseTitle: data.history_match.release_title ?? null,
          mediaType: data.history_match.media_type ?? null,
          protocol: data.history_match.protocol ?? null,
        }
      : null,
  };
}

/** The 409 from /portal/download when rTorrent already has the torrent. */
export function alreadyInClientDetail(err: unknown): { message: string } | null {
  if (!(err instanceof ApiError) || err.status !== 409) return null;
  const d = err.detail as { code?: string; message?: string } | null;
  if (!d || typeof d !== 'object' || d.code !== 'already_in_client') return null;
  return { message: d.message ?? err.message };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function mapHistoryItem(item: any): HistoryItem {
  return {
    id: item.id,
    title: item.title,
    author: item.author,
    downloadId: item.download_id,
    releaseTitle: item.release_title,
    indexer: item.indexer,
    protocol: item.protocol,
    source: item.source,
    mediaType: item.media_type,
    status: item.status,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
    error: item.error,
  };
}

export async function login(accessCode: string): Promise<AuthResponse> {
  if (MOCK_MODE) return mockAuth(accessCode);
  const res = await fetch('/portal/auth', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ access_code: accessCode }),
  });
  if (res.status === 401) {
    return { ok: false };
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const data = await handleResponse<any>(res);
  return {
    ok: data.ok,
    sessionToken: data.session_token,
    expiresAt: data.expires_at,
  };
}

export async function logout(): Promise<void> {
  if (MOCK_MODE) return;
  await fetch('/portal/logout', { method: 'POST', credentials: 'include' });
}

export async function getReleases(title: string, author: string): Promise<ReleasesResponse> {
  if (MOCK_MODE) return mockGetReleases(title, author);
  const params = new URLSearchParams();
  if (title.trim()) params.set('title', title.trim());
  if (author.trim()) params.set('author', author.trim());
  const res = await fetch(`/portal/releases?${params.toString()}`, {
    credentials: 'include',
  });
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const data = await handleResponse<any>(res);
  return mapReleases(data);
}

export async function downloadRelease(args: {
  title: string;
  author: string;
  releaseTitle: string;
  indexer: string;
  protocol: string;
  downloadUrl: string;
  mediaType: MediaType;
}): Promise<DownloadResponse> {
  if (MOCK_MODE) return mockDownload(args);
  const res = await fetch('/portal/download', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({
      title: args.title,
      author: args.author,
      release_title: args.releaseTitle,
      indexer: args.indexer,
      protocol: args.protocol,
      download_url: args.downloadUrl,
      media_type: args.mediaType,
    }),
  });
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const data = await handleResponse<any>(res);
  return {
    ok: data.ok,
    recordId: data.record_id,
    downloadId: data.download_id,
    message: data.message,
  };
}

export async function getMamStatus(): Promise<MamStatus> {
  if (MOCK_MODE) return mockGetMamStatus();
  const res = await fetch('/portal/mam-status', { credentials: 'include' });
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const data = await handleResponse<any>(res);
  return {
    unsatisfied: data.unsatisfied ?? null,
    limit: data.limit,
    blockThreshold: data.block_threshold,
    slotsFree: data.slots_free ?? null,
    blocked: !!data.blocked,
    nextFreeAt: data.next_free_at ?? null,
    serverTime: data.server_time,
  };
}

export async function getHistory(limit = 500): Promise<HistoryItem[]> {
  if (MOCK_MODE) return mockGetHistory();
  const res = await fetch(`/portal/history?limit=${limit}`, { credentials: 'include' });
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const data = await handleResponse<any>(res);
  return (data.items ?? []).map(mapHistoryItem);
}

export async function getSeeding(): Promise<SeedingItem[]> {
  if (MOCK_MODE) return mockGetSeeding();
  const res = await fetch('/portal/seeding', { credentials: 'include' });
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const data = await handleResponse<any>(res);
  return (data.seeding ?? []).map((s: { hash: string; finished_at?: number }) => ({
    hash: s.hash,
    finishedAt: s.finished_at,
  }));
}

export async function getGoodreadsProfiles(): Promise<GoodreadsProfile[]> {
  if (MOCK_MODE) return mockGetGoodreadsProfiles();
  const res = await fetch('/portal/goodreads-profiles', { credentials: 'include' });
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const data = await handleResponse<any>(res);
  return data.profiles ?? [];
}

export async function addGoodreadsProfile(body: {
  name: string;
  user_id: string;
  shelf: string;
  sync_from?: string | null;
}): Promise<void> {
  if (MOCK_MODE) {
    await mockAddGoodreadsProfile(body);
    return;
  }
  await handleResponse(
    await fetch('/portal/goodreads-profiles', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(body),
    })
  );
}

export async function deleteGoodreadsProfile(profileId: string): Promise<void> {
  if (MOCK_MODE) {
    await mockDeleteGoodreadsProfile(profileId);
    return;
  }
  await handleResponse(
    await fetch(`/portal/goodreads-profiles/${profileId}`, {
      method: 'DELETE',
      credentials: 'include',
    })
  );
}

// --- List import ---

/** Extract the structured {code, message} from an extraction error, if that's what it is. */
export function extractErrorDetail(err: unknown): { code: ExtractErrorCode; message: string } | null {
  if (!(err instanceof ApiError)) return null;
  const d = err.detail as { code?: string; message?: string } | null;
  if (!d || typeof d !== 'object' || typeof d.code !== 'string') return null;
  return { code: d.code as ExtractErrorCode, message: d.message ?? err.message };
}

export async function extractList(input: { url: string } | { text: string }): Promise<ImportExtractResponse> {
  if (MOCK_MODE) return mockExtractList(input);
  const res = await fetch('/portal/import/extract', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(input),
  });
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const data = await handleResponse<any>(res);
  return {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    books: (data.books ?? []).map((b: any) => ({
      title: b.title ?? '',
      author: b.author ?? '',
      confidence: b.confidence === 'low' ? 'low' : 'high',
    })),
    source: data.source,
    sourceTitle: data.source_title ?? null,
  };
}

export async function startResolve(
  books: { title: string; author: string }[],
  includeAudiobooks = true,
): Promise<{ jobId: string; total: number }> {
  if (MOCK_MODE) return mockStartResolve(books, includeAudiobooks);
  const res = await fetch('/portal/import/resolve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ books, include_audiobooks: includeAudiobooks }),
  });
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const data = await handleResponse<any>(res);
  return { jobId: data.job_id, total: data.total };
}

export async function getResolveStatus(jobId: string): Promise<ImportResolveStatus> {
  if (MOCK_MODE) return mockGetResolveStatus(jobId);
  const res = await fetch(`/portal/import/resolve/${encodeURIComponent(jobId)}`, { credentials: 'include' });
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const data = await handleResponse<any>(res);
  return {
    jobId: data.job_id,
    done: !!data.done,
    total: data.total,
    completed: data.completed,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    results: (data.results ?? []).map((r: any) => ({
      index: r.index,
      title: r.title,
      author: r.author ?? '',
      status: r.status,
      releases: r.releases ? mapReleases(r.releases) : null,
      error: r.error ?? null,
    })),
  };
}

export async function cancelResolve(jobId: string): Promise<void> {
  if (MOCK_MODE) {
    await mockCancelResolve(jobId);
    return;
  }
  // Best-effort: the job may already have expired.
  await fetch(`/portal/import/resolve/${encodeURIComponent(jobId)}`, {
    method: 'DELETE',
    credentials: 'include',
  }).catch(() => undefined);
}
