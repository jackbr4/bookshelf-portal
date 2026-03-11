const SESSION_KEY = 'portal_session';

export interface SessionData {
  expiresAt: number;
}

export function saveSession(expiresAt: string): void {
  const data: SessionData = { expiresAt: new Date(expiresAt).getTime() };
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(data));
}

export function clearSession(): void {
  sessionStorage.removeItem(SESSION_KEY);
}

export function isSessionValid(): boolean {
  const raw = sessionStorage.getItem(SESSION_KEY);
  if (!raw) return false;
  try {
    const data: SessionData = JSON.parse(raw);
    return data.expiresAt > Date.now();
  } catch {
    return false;
  }
}
