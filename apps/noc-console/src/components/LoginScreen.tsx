import { useState, FormEvent } from 'react';
import { login } from '../lib/auth';
import type { Session } from '../lib/auth';

interface LoginScreenProps {
  onLogin: (session: Session) => void;
}

export function LoginScreen({ onLogin }: LoginScreenProps) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError('');
    setPending(true);
    try {
      const session = await login(username, password);
      onLogin(session);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-bento-bg px-4">
      <div className="w-full max-w-md bg-white border border-bento-border rounded-lg p-8">
        <h1 className="text-2xl font-semibold text-navy mb-6 text-center">
          NetSentinel NOC Console
        </h1>
        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <div>
            <label htmlFor="username" className="block text-sm font-medium text-slate-600 mb-1">
              Username
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full bg-bento-bg border border-bento-border rounded-md px-3 py-2 text-navy placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent"
              placeholder="Enter username"
              required
              autoComplete="username"
              disabled={pending}
            />
          </div>
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-slate-600 mb-1">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-bento-bg border border-bento-border rounded-md px-3 py-2 text-navy placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent"
              placeholder="Enter password"
              required
              autoComplete="current-password"
              disabled={pending}
            />
          </div>
          {error && (
            <div
              role="alert"
              className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-md p-3"
            >
              {error}
            </div>
          )}
          <button
            type="submit"
            disabled={pending}
            className="w-full bg-sky-600 hover:bg-sky-500 disabled:bg-sky-600/50 disabled:cursor-not-allowed text-white font-medium py-2 px-4 rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 focus:ring-offset-slate-900"
          >
            {pending ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
        <p className="mt-6 text-xs text-slate-600 text-center">
          Demo users: viewer / operator / admin (password = username). Synthetic data only.
        </p>
      </div>
    </div>
  );
}
