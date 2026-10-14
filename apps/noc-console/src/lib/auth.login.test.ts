import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { installAuthFetch, loadSession, login, withToken } from './auth';

// Regression (Mac demo): login() didn't persist the session, so every /api call went out
// without a token (401 -> back to login) and the WebSockets got 403.
describe('login persists the session', () => {
  let uninstall: () => void = () => {};

  beforeEach(() => {
    sessionStorage.clear();
  });

  afterEach(() => {
    uninstall();
    vi.unstubAllGlobals();
    sessionStorage.clear();
  });

  it('stores the session, adds the Authorization header and the WS token', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url === '/api/auth/login') {
        return new Response(
          JSON.stringify({
            accessToken: 'jwt-abc',
            expiresIn: 3600,
            username: 'operator',
            role: 'operator',
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        );
      }
      return new Response('{}', { status: 200 });
    });
    vi.stubGlobal('fetch', fetchMock);
    uninstall = installAuthFetch(() => {});

    const session = await login('operator', 'operator');

    expect(session.token).toBe('jwt-abc');
    expect(loadSession()).toMatchObject({
      token: 'jwt-abc',
      username: 'operator',
      role: 'operator',
    });

    await fetch('/api/incidents');
    const [, init] = fetchMock.mock.calls.at(-1) as unknown as [string, RequestInit];
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer jwt-abc');

    // The login call itself must not carry a (stale) bearer token
    const [, loginInit] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(new Headers(loginInit.headers).has('Authorization')).toBe(false);

    expect(withToken('ws://localhost:5173/ws/alarms')).toBe(
      'ws://localhost:5173/ws/alarms?token=jwt-abc',
    );
  });

  it('does not store a session when login fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('{}', { status: 401 })),
    );
    await expect(login('operator', 'wrong')).rejects.toThrow('Invalid username or password');
    expect(loadSession()).toBeNull();
  });
});
