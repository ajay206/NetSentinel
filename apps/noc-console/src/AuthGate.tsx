import React, { useCallback, useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import App from './App';
import { LoginScreen } from './components/LoginScreen';
import { clearSession, installAuthFetch, loadSession, type Session } from './lib/auth';

/**
 * W11: shows the login screen until there is a session, adds the bearer token to every
 * /api call (and ?token= to WebSockets), and drops back to login on any 401.
 */
export const AuthGate: React.FC = () => {
  const queryClient = useQueryClient();
  const [session, setSession] = useState<Session | null>(() => loadSession());

  const logout = useCallback(() => {
    clearSession();
    queryClient.clear();
    setSession(null);
  }, [queryClient]);

  // Child effects run before this one, so App's first queries could go out without the bearer
  // token. Mount App only after the fetch wrapper is installed.
  const [fetchReady, setFetchReady] = useState(false);
  useEffect(() => {
    const uninstall = installAuthFetch(logout);
    setFetchReady(true);
    return uninstall;
  }, [logout]);

  if (!session) {
    return <LoginScreen onLogin={setSession} />;
  }
  if (!fetchReady) return null;
  // key: remount on user change so WebSockets reconnect with the new token
  return <App key={session.username} session={session} onLogout={logout} />;
};

export default AuthGate;
