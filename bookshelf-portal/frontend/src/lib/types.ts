export type ItemStatus = 'available' | 'already_in_library' | 'already_monitored';

export interface BookResult {
  id: string;
  title: string;
  author: string;
  year?: number;
  seriesName?: string;
  coverUrl?: string | null;
  status: ItemStatus;
  foreignAuthorId?: string | null;
  foreignEditionId?: string | null;
}

export interface SeriesResult {
  id: string;
  title: string;
  author: string;
  bookCount?: number;
  coverUrl?: string | null;
  status: ItemStatus;
}

export interface SearchResults {
  books: BookResult[];
  series: SeriesResult[];
  filteredBooks: BookResult[];
}

export interface ToastState {
  kind: 'success' | 'info' | 'error';
  message: string;
  subMessage?: string;
  actionLabel?: string;
  onAction?: () => void;
}

export interface AuthResponse {
  ok: boolean;
  sessionToken?: string;
  expiresAt?: string;
}

export interface AddResponse {
  ok: boolean;
  message: string;
}
