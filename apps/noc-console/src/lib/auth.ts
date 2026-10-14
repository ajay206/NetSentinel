export type Role = 'viewer' | 'operator' | 'admin';

export interface Session {
  token: string;
  username: string;
  role: Role;
  expiresAt: number;
}

const SESSION_KEY = 'ns.session';

export function loadSession(): Session | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const session = JSON.parse(raw) as Session;
    if (Date.now() >= session.expiresAt) {
      clearSession();
      return null;
    }
    return session;
  } catch {
    return null;
  }
}

export function saveSession(session: Session): void {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function clearSession(): void {
  sessionStorage.removeItem(SESSION_KEY);
}

export function roleAtLeast(role: Role | undefined, needed: Role): boolean {
  const order: Role[] = ['viewer', 'operator', 'admin'];
  if (!role) return false;
  return order.indexOf(role) >= order.indexOf(needed);
}

export async function login(username: string, password: string): Promise<Session> {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });

  if (res.status === 401) {
    throw new Error('Invalid username or password');
  }
  if (res.status === 423) {
    throw new Error('Account locked after too many failed attempts; try later or ask an admin');
  }
  if (res.status === 403) {
    throw new Error('Account disabled; ask an admin');
  }
  if (res.status === 503) {
    throw new Error('Sign-in is starting up; try again in a few seconds');
  }
  if (res.status === 429) {
    throw new Error('Too many attempts, wait a minute');
  }
  if (!res.ok) {
    throw new Error(`Login failed (${res.status})`);
  }

  const data = (await res.json()) as {
    accessToken: string;
    expiresIn: number;
    username: string;
    role: Role;
  };

  const session: Session = {
    token: data.accessToken,
    username: data.username,
    role: data.role,
    expiresAt: Date.now() + data.expiresIn * 1000,
  };
  // Persist before returning: the fetch wrapper and the WS URLs read the token from storage.
  saveSession(session);
  return session;
}

let originalFetch: typeof fetch = globalThis.fetch;
let isInstalled = false;

export function installAuthFetch(onUnauthorized: () => void): () => void {
  if (isInstalled) {
    return () => {};
  }
  originalFetch = globalThis.fetch;
  isInstalled = true;

  globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const session = loadSession();
    const url =
      typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    const isApi = url.startsWith('/api');
    const isLogin = url === '/api/auth/login';

    const headers = new Headers(init?.headers);
    if (isApi && !isLogin && session && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${session.token}`);
    }

    const response = await originalFetch(input, { ...init, headers });

    if (response.status === 401 && isApi && !isLogin) {
      clearSession();
      onUnauthorized();
    }

    return response;
  };

  return () => {
    globalThis.fetch = originalFetch;
    isInstalled = false;
  };
}

export function withToken(wsUrl: string): string {
  const session = loadSession();
  if (!session) return wsUrl;
  const separator = wsUrl.includes('?') ? '&' : '?';
  return `${wsUrl}${separator}token=${encodeURIComponent(session.token)}`;
}

export const AUTH_EVENT = 'ns-auth-changed';
