import type { SearchResults, AuthResponse, AddResponse, BookResult, SeriesResult } from '../lib/types';

const MOCK_PASSWORD = 'family';

const MOCK_BOOKS: BookResult[] = [
  { id: 'book_1', title: 'Dune', author: 'Frank Herbert', year: 1965, seriesName: 'Dune', status: 'available' },
  { id: 'book_2', title: 'Dune Messiah', author: 'Frank Herbert', year: 1969, seriesName: 'Dune', status: 'already_in_library' },
  { id: 'book_3', title: 'The Way of Kings', author: 'Brandon Sanderson', year: 2010, seriesName: 'The Stormlight Archive', status: 'available' },
  { id: 'book_4', title: 'Words of Radiance', author: 'Brandon Sanderson', year: 2014, seriesName: 'The Stormlight Archive', status: 'already_monitored' },
  { id: 'book_5', title: 'Project Hail Mary', author: 'Andy Weir', year: 2021, status: 'available' },
  { id: 'book_6', title: 'The Martian', author: 'Andy Weir', year: 2011, status: 'already_in_library' },
];

const MOCK_SERIES: SeriesResult[] = [
  { id: 'series_1', title: 'Dune Chronicles', author: 'Frank Herbert', bookCount: 6, status: 'already_monitored' },
  { id: 'series_2', title: 'The Stormlight Archive', author: 'Brandon Sanderson', bookCount: 5, status: 'available' },
  { id: 'series_3', title: 'The Expanse', author: 'James S.A. Corey', bookCount: 9, status: 'available' },
  { id: 'series_4', title: 'Mistborn', author: 'Brandon Sanderson', bookCount: 7, status: 'already_monitored' },
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

export async function mockSearch(query: string): Promise<SearchResults> {
  await delay(800);
  const q = query.toLowerCase();
  const books = MOCK_BOOKS.filter(b =>
    b.title.toLowerCase().includes(q) || b.author.toLowerCase().includes(q)
  );
  const series = MOCK_SERIES.filter(s =>
    s.title.toLowerCase().includes(q) || s.author.toLowerCase().includes(q)
  );
  return { books, series };
}

export async function mockAddBook(_bookId: string): Promise<AddResponse> {
  await delay(500);
  return { ok: true, message: 'Book added successfully' };
}

export async function mockAddSeries(_seriesId: string): Promise<AddResponse> {
  await delay(500);
  return { ok: true, message: 'Series added successfully' };
}
