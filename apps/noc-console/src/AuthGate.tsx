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

  useEffect(() => installAuthFetch(logout), [logout]);

  if (!session) {
    return <LoginScreen onLogin={setSession} />;
  }
  // key: remount on user change so WebSockets reconnect with the new token
  return <App key={session.username} session={session} onLogout={logout} />;
};

export default AuthGate;
