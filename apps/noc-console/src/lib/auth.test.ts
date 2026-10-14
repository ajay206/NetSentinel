import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  loadSession,
  saveSession,
  clearSession,
  roleAtLeast,
  installAuthFetch,
  withToken,
  AUTH_EVENT,
} from './auth';
import type { Session } from './auth';

describe('lib/auth', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    sessionStorage.clear();
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    sessionStorage.clear();
  });

  describe('roleAtLeast', () => {
    it('returns true when role meets needed', () => {
      expect(roleAtLeast('admin', 'operator')).toBe(true);
      expect(roleAtLeast('operator', 'operator')).toBe(true);
      expect(roleAtLeast('viewer', 'viewer')).toBe(true);
    });

    it('returns false when role below needed', () => {
      expect(roleAtLeast('viewer', 'operator')).toBe(false);
      expect(roleAtLeast('operator', 'admin')).toBe(false);
    });

    it('returns false for undefined role', () => {
      expect(roleAtLeast(undefined, 'viewer')).toBe(false);
    });
  });

  describe('session expiry', () => {
    it('loadSession returns null when expired', () => {
      const session: Session = {
        token: 'abc',
        username: 'test',
        role: 'viewer',
        expiresAt: Date.now() - 1000,
      };
      saveSession(session);
      expect(loadSession()).toBeNull();
    });

    it('loadSession returns session when valid', () => {
      const session: Session = {
        token: 'abc',
        username: 'test',
        role: 'viewer',
        expiresAt: Date.now() + 10000,
      };
      saveSession(session);
      expect(loadSession()).toEqual(session);
    });

    it('clearSession removes session', () => {
      const session: Session = {
        token: 'abc',
        username: 'test',
        role: 'viewer',
        expiresAt: Date.now() + 10000,
      };
      saveSession(session);
      clearSession();
      expect(loadSession()).toBeNull();
    });
  });

  describe('installAuthFetch', () => {
    it('adds Authorization header to /api requests', async () => {
      const session: Session = {
        token: 'token123',
        username: 'test',
        role: 'viewer',
        expiresAt: Date.now() + 10000,
      };
      saveSession(session);

      const mockFetch = vi.fn().mockResolvedValue(new Response(null, { status: 200 }));
      vi.stubGlobal('fetch', mockFetch);

      const uninstall = installAuthFetch(() => {});
      await fetch('/api/alarms');
      uninstall();

      const init = mockFetch.mock.calls[0][1] as RequestInit;
      expect(new Headers(init.headers).get('Authorization')).toBe('Bearer token123');
    });

    it('does not add header to non-/api requests', async () => {
      const session: Session = {
        token: 'token123',
        username: 'test',
        role: 'viewer',
        expiresAt: Date.now() + 10000,
      };
      saveSession(session);

      const mockFetch = vi.fn().mockResolvedValue(new Response(null, { status: 200 }));
      vi.stubGlobal('fetch', mockFetch);

      const uninstall = installAuthFetch(() => {});
      await fetch('/health');
      uninstall();

      const call = mockFetch.mock.calls[0];
      const headers = call[1]?.headers as Headers | undefined;
      expect(headers?.get('Authorization')).toBeNull();
    });

    it('does not override existing Authorization header', async () => {
      const session: Session = {
        token: 'token123',
        username: 'test',
        role: 'viewer',
        expiresAt: Date.now() + 10000,
      };
      saveSession(session);

      const mockFetch = vi.fn().mockResolvedValue(new Response(null, { status: 200 }));
      vi.stubGlobal('fetch', mockFetch);

      const uninstall = installAuthFetch(() => {});
      await fetch('/api/alarms', {
        headers: { Authorization: 'Bearer custom' },
      });
      uninstall();

      const call = mockFetch.mock.calls[0];
      const headers = call[1]?.headers as Headers | undefined;
      expect(headers?.get('Authorization')).toBe('Bearer custom');
    });

    it('clears session and calls callback on 401 for /api (not login)', async () => {
      const session: Session = {
        token: 'token123',
        username: 'test',
        role: 'viewer',
        expiresAt: Date.now() + 10000,
      };
      saveSession(session);

      const onUnauthorized = vi.fn();
      const mockFetch = vi.fn().mockResolvedValue(new Response(null, { status: 401 }));
      vi.stubGlobal('fetch', mockFetch);

      const uninstall = installAuthFetch(onUnauthorized);
      await fetch('/api/alarms');
      uninstall();

      expect(onUnauthorized).toHaveBeenCalledTimes(1);
      expect(loadSession()).toBeNull();
    });

    it('does not clear session on 401 for /api/auth/login', async () => {
      const session: Session = {
        token: 'token123',
        username: 'test',
        role: 'viewer',
        expiresAt: Date.now() + 10000,
      };
      saveSession(session);

      const onUnauthorized = vi.fn();
      const mockFetch = vi.fn().mockResolvedValue(new Response(null, { status: 401 }));
      vi.stubGlobal('fetch', mockFetch);

      const uninstall = installAuthFetch(onUnauthorized);
      await fetch('/api/auth/login', { method: 'POST' });
      uninstall();

      expect(onUnauthorized).not.toHaveBeenCalled();
      expect(loadSession()).toEqual(session);
    });
  });

  describe('withToken', () => {
    it('appends token query param when session exists', () => {
      const session: Session = {
        token: 'token123',
        username: 'test',
        role: 'viewer',
        expiresAt: Date.now() + 10000,
      };
      saveSession(session);
      expect(withToken('wss://example.com/ws')).toBe('wss://example.com/ws?token=token123');
      expect(withToken('wss://example.com/ws?foo=bar')).toBe(
        'wss://example.com/ws?foo=bar&token=token123',
      );
    });

    it('returns original url when no session', () => {
      clearSession();
      expect(withToken('wss://example.com/ws')).toBe('wss://example.com/ws');
    });
  });

  describe('AUTH_EVENT', () => {
    it('is exported as constant', () => {
      expect(AUTH_EVENT).toBe('ns-auth-changed');
    });
  });
});
