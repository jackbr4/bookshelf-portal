import type { SearchResults, AuthResponse, AddResponse, BookResult, SeriesResult } from './types';
import { mockAuth, mockSearch, mockAddBook, mockAddSeries } from '../mocks/mockApi';

const MOCK_MODE = import.meta.env.VITE_MOCK_MODE === 'true';

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.status === 401) {
    throw new Error('SESSION_EXPIRED');
  }
  if (res.status === 409) {
    throw new Error('DUPLICATE');
  }
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    let detail = `HTTP ${res.status}`;
    try {
      const json = JSON.parse(text);
      detail = json.detail || json.message || text || detail;
    } catch {
      if (text) detail = text;
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

// Map snake_case backend fields to camelCase frontend types
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function mapBook(b: any): BookResult {
  return {
    id: b.id,
    title: b.title,
    author: b.author,
    year: b.year,
    seriesName: b.series_name,
    coverUrl: b.cover_url,
    status: b.status,
    foreignAuthorId: b.foreign_author_id,
    foreignEditionId: b.foreign_edition_id,
  };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function mapSeries(s: any): SeriesResult {
  return {
    id: s.id,
    title: s.title,
    author: s.author,
    bookCount: s.book_count,
    coverUrl: s.cover_url,
    status: s.status,
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

export async function search(query: string): Promise<SearchResults> {
  if (MOCK_MODE) return mockSearch(query);
  const res = await fetch(`/portal/search?q=${encodeURIComponent(query)}`, {
    credentials: 'include',
  });
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const data = await handleResponse<any>(res);
  return {
    books: (data.books ?? []).map(mapBook),
    series: (data.series ?? []).map(mapSeries),
  };
}

export async function addBook(bookId: string, title?: string, author?: string, foreignAuthorId?: string | null, foreignEditionId?: string | null): Promise<AddResponse> {
  if (MOCK_MODE) return mockAddBook(bookId);
  const res = await fetch('/portal/request/book', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ book_id: bookId, title, author, foreign_author_id: foreignAuthorId, foreign_edition_id: foreignEditionId }),
  });
  return handleResponse<AddResponse>(res);
}

export async function addSeries(seriesId: string): Promise<AddResponse> {
  if (MOCK_MODE) return mockAddSeries(seriesId);
  const res = await fetch('/portal/request/series', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ series_id: seriesId }),
  });
  return handleResponse<AddResponse>(res);
}
