import React, { useEffect, useState } from 'react';
import { Card } from './ui/Card';
import { passwordProblems, passwordStrength, STRENGTH_LABELS } from '../lib/passwordPolicy';

type ChangePasswordResult = {
  accessToken: string;
  expiresIn: number;
  username: string;
  role: string;
};

export const ChangePasswordDialog: React.FC<{
  open: boolean;
  username: string;
  onClose: () => void;
  onChanged: (r: ChangePasswordResult) => void;
}> = ({ open, username, onClose, onChanged }) => {
  const [current, setCurrent] = useState('');
  const [newPw, setNewPw] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) {
      setCurrent('');
      setNewPw('');
      setConfirm('');
      setError(null);
      setSubmitting(false);
    }
  }, [open]);

  const problems = passwordProblems(newPw, username);
  const strength = passwordStrength(newPw);

  const passwordsMatch = confirm === '' || newPw === confirm;
  const newDiffers = newPw !== '' && newPw !== current;

  const canSubmit = Boolean(
    current &&
    newPw &&
    confirm &&
    passwordsMatch &&
    newDiffers &&
    problems.length === 0 &&
    !submitting,
  );

  const handleSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const resp = await fetch('/api/auth/password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ currentPassword: current, newPassword: newPw }),
      });
      const data = (await resp.json().catch(() => ({}))) as Partial<ChangePasswordResult> & {
        detail?: string;
      };
      if (!resp.ok || !data.accessToken) {
        throw new Error(data.detail ?? 'Password change failed');
      }
      onChanged(data as ChangePasswordResult);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Password change failed');
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-label="Change password"
      className="fixed inset-0 flex items-center justify-center z-50 bg-black/60"
    >
      <Card
        title="Change password"
        subtitle="Other sessions are signed out when the password changes."
        className="w-full max-w-md text-slate-100"
      >
        <form className="space-y-4" onSubmit={handleSubmit} noValidate>
          <div>
            <label className="block text-sm font-medium mb-1" htmlFor="current-pw">
              Current password
            </label>
            <input
              id="current-pw"
              type="password"
              autoComplete="current-password"
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              className="w-full rounded px-2 py-1 bg-slate-700 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1" htmlFor="new-pw">
              New password
            </label>
            <input
              id="new-pw"
              type="password"
              autoComplete="new-password"
              value={newPw}
              onChange={(e) => setNewPw(e.target.value)}
              className="w-full rounded px-2 py-1 bg-slate-700 focus:outline-none"
            />
            <div data-testid="pw-strength" className="mt-2 flex items-center gap-2 text-xs">
              <div className="flex flex-1 gap-1" aria-hidden="true">
                {[1, 2, 3, 4].map((i) => (
                  <span
                    key={i}
                    className={`h-1.5 flex-1 rounded ${
                      i <= strength
                        ? ['bg-red-500', 'bg-orange-500', 'bg-yellow-400', 'bg-emerald-500'][
                            strength - 1
                          ]
                        : 'bg-slate-700'
                    }`}
                  />
                ))}
              </div>
              <span className="w-16 text-right text-slate-300">{STRENGTH_LABELS[strength]}</span>
            </div>
            {newPw && problems.length > 0 && (
              <ul
                data-testid="pw-problems"
                className="mt-1 text-xs text-amber-300 list-disc list-inside"
              >
                <li className="list-none text-slate-400">Still needs:</li>
                {problems.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium mb-1" htmlFor="confirm-pw">
              Confirm new password
            </label>
            <input
              id="confirm-pw"
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className="w-full rounded px-2 py-1 bg-slate-700 focus:outline-none"
            />
            {confirm && !passwordsMatch && (
              <div className="mt-1 text-xs text-red-400">Passwords do not match</div>
            )}
            {newPw && current && newPw === current && (
              <div className="mt-1 text-xs text-red-400">
                New password must differ from the current one
              </div>
            )}
          </div>

          {error && (
            <div
              role="alert"
              className="text-sm text-red-300 bg-red-950 border border-red-800 p-2 rounded"
            >
              {error}
            </div>
          )}

          <div className="flex justify-end space-x-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1 rounded bg-slate-600 hover:bg-slate-500"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!canSubmit}
              className={`px-3 py-1 rounded ${
                canSubmit
                  ? 'bg-sky-600 hover:bg-sky-500'
                  : 'bg-slate-700 text-slate-400 cursor-not-allowed'
              }`}
            >
              Change password
            </button>
          </div>
        </form>
      </Card>
    </div>
  );
};
