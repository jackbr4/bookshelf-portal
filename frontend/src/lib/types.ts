export type MediaType = 'ebook' | 'audiobook';
export type ViewMode = 'simple' | 'detailed';
export type MediaFilter = 'all' | 'ebook' | 'audiobook';
export type StatFilter = 'all' | 'imported' | 'active' | 'errors' | 'seeding';

export interface ReleaseItem {
  guid: string;
  title: string;
  indexer: string;
  protocol: string;
  sizeMb: number;
  detectedFormat?: string | null;
  seeders?: number | null;
  ageDays?: number | null;
  downloadUrl: string;
  publishDate?: string | null;
  score: number;
  rejected?: boolean;
  rejectReason?: string | null;
}

export interface ReleasesResponse {
  ebookAccepted: ReleaseItem[];
  ebookRejected: ReleaseItem[];
  audiobookAccepted: ReleaseItem[];
  audiobookRejected: ReleaseItem[];
  calibreTitle?: string | null;
  audiobooksTitle?: string | null;
}

export interface DownloadResponse {
  ok: boolean;
  recordId: string;
  downloadId: string;
  message: string;
}

export interface HistoryItem {
  id: string;
  title: string;
  author: string;
  downloadId?: string | null;
  releaseTitle?: string | null;
  indexer?: string | null;
  protocol?: string | null;
  source?: string | null;
  mediaType?: string | null;
  status: string;
  createdAt: string;
  updatedAt: string;
  error?: string | null;
}

export interface SeedingItem {
  hash: string;
  finishedAt?: number;
}

export interface GoodreadsProfile {
  id: string;
  name: string;
  user_id: string;
  shelf: string;
  sync_from?: string | null;
  active?: number;
  created_at?: string;
}

export interface MamStatus {
  /** null = rTorrent unreachable; status unknown (backend fails closed on dispatch). */
  unsatisfied: number | null;
  limit: number;
  blockThreshold: number;
  /** Free slots relative to blockThreshold; null when unsatisfied is null. */
  slotsFree: number | null;
  /** True when a torrent dispatch would be refused (at threshold, or status unverifiable). */
  blocked: boolean;
  /** Unix seconds when the next slot frees; null = all unsatisfied torrents still downloading. */
  nextFreeAt: number | null;
  /** Unix seconds on the server at response time — use to offset the client clock. */
  serverTime: number;
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
