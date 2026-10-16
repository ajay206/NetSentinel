import React, { useState } from 'react';
import { Tip } from '../../components/ui/Tooltip';
import { TIPS } from '../../lib/tooltips';
import { Card, StateMessage } from '../../components/ui/Card';
import { useAdminUserAction, useAdminUsers, type AdminUser } from '../../hooks/useAdmin';
import { passwordProblems } from '../../lib/passwordPolicy';
import { ROLE_STYLE } from '../../lib/rbac';

const ROLES: AdminUser['role'][] = ['viewer', 'operator', 'admin'];
const SELF = 'You cannot change your own account here';
const input = 'rounded border border-bento-border bg-bento-bg px-2 py-1 text-sm text-navy';
const btn =
  'rounded px-2 py-0.5 text-xs border border-bento-border text-navy hover:bg-bento-bg disabled:opacity-40 disabled:cursor-not-allowed';

/** Step 13b (admin): create users, change roles, disable/enable, unlock and reset passwords. */
export const AdminUsers: React.FC<{ currentUser: string }> = ({ currentUser }) => {
  const users = useAdminUsers();
  const action = useAdminUserAction();
  const [form, setForm] = useState({
    username: '',
    role: 'viewer' as AdminUser['role'],
    password: '',
  });
  const [resetFor, setResetFor] = useState<string | null>(null);
  const [resetPw, setResetPw] = useState('');
  const createProblems = form.password ? passwordProblems(form.password, form.username) : [];

  const create = (e: React.FormEvent) => {
    e.preventDefault();
    action.mutate(
      { kind: 'create', ...form, username: form.username.trim().toLowerCase() },
      {
        onSuccess: () => setForm({ username: '', role: 'viewer', password: '' }),
      },
    );
  };

  let body: React.ReactNode;
  if (users.isLoading) body = <StateMessage kind="loading">Loading users…</StateMessage>;
  else if (users.isError)
    body = <StateMessage kind="error">Users unavailable: {users.error.message}</StateMessage>;
  else if (!users.data?.length) body = <StateMessage kind="empty">No users yet.</StateMessage>;
  else
    body = (
      <div className="ns-table-wrap">
        <table className="w-full text-sm" data-testid="users-table">
          <thead className="ns-thead">
            <tr className="text-left">
              <th className="px-2 py-1.5">
                <Tip tip={TIPS.colUser}>User</Tip>
              </th>
              <th className="px-2 py-1.5">
                <Tip tip={TIPS.colRole}>Role</Tip>
              </th>
              <th className="px-2 py-1.5">
                <Tip tip={TIPS.colStatus}>Status</Tip>
              </th>
              <th className="px-2 py-1.5">
                <Tip tip={TIPS.colFailedLogins}>Failed logins</Tip>
              </th>
              <th className="px-2 py-1.5">
                <Tip tip={TIPS.colActions}>Actions</Tip>
              </th>
            </tr>
          </thead>
          <tbody>
            {users.data.map((u) => {
              const self = u.username === currentUser;
              return (
                <tr key={u.username} className="border-t border-bento-border align-top">
                  <td className="px-2 py-2 font-mono text-navy">
                    {u.username}
                    {self && <span className="ml-1 text-xs text-slate-600">(you)</span>}
                  </td>
                  <td className="px-2 py-2">
                    <select
                      aria-label={`Role for ${u.username}`}
                      value={u.role}
                      disabled={self || action.isPending}
                      title={self ? SELF : undefined}
                      onChange={(e) =>
                        action.mutate({
                          kind: 'update',
                          username: u.username,
                          role: e.target.value as AdminUser['role'],
                        })
                      }
                      className={`${input} ${ROLE_STYLE[u.role]}`}
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>
                          {r}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-2 py-2">
                    <span
                      className={`rounded px-2 py-0.5 text-xs ${
                        u.disabled
                          ? 'bg-slate-200 text-slate-600'
                          : u.locked
                            ? 'bg-red-500/15 text-red-700'
                            : 'bg-emerald-500/15 text-emerald-700'
                      }`}
                    >
                      {u.disabled ? 'Disabled' : u.locked ? 'Locked' : 'Active'}
                    </span>
                  </td>
                  <td className="px-2 py-2 tabular-nums text-bento-muted">{u.failedLogins}</td>
                  <td className="px-2 py-2">
                    <div className="flex flex-wrap gap-1.5">
                      <button
                        type="button"
                        className={btn}
                        disabled={self || action.isPending}
                        title={self ? SELF : undefined}
                        onClick={() =>
                          action.mutate({
                            kind: 'update',
                            username: u.username,
                            disabled: !u.disabled,
                          })
                        }
                      >
                        {u.disabled ? 'Enable' : 'Disable'}
                      </button>
                      {u.locked && (
                        <button
                          type="button"
                          className={btn}
                          onClick={() =>
                            action.mutate({
                              kind: 'unlock',
                              username: u.username,
                            })
                          }
                        >
                          Unlock
                        </button>
                      )}
                      <button
                        type="button"
                        className={btn}
                        onClick={() => {
                          setResetFor(resetFor === u.username ? null : u.username);
                          setResetPw('');
                        }}
                      >
                        Reset password
                      </button>
                    </div>
                    {resetFor === u.username && (
                      <div className="mt-2 flex flex-wrap items-center gap-1.5">
                        <input
                          type="password"
                          autoComplete="new-password"
                          aria-label={`New password for ${u.username}`}
                          value={resetPw}
                          onChange={(e) => setResetPw(e.target.value)}
                          className={input}
                        />
                        <button
                          type="button"
                          className={btn}
                          disabled={passwordProblems(resetPw, u.username).length > 0}
                          title={passwordProblems(resetPw, u.username).join(', ') || undefined}
                          onClick={() =>
                            action.mutate(
                              {
                                kind: 'reset',
                                username: u.username,
                                newPassword: resetPw,
                              },
                              { onSuccess: () => setResetFor(null) },
                            )
                          }
                        >
                          Save
                        </button>
                        <button type="button" className={btn} onClick={() => setResetFor(null)}>
                          Cancel
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );

  return (
    <Card
      title="User management"
      subtitle="Create users, change roles, disable, unlock and reset passwords."
      info={TIPS.panelUsers}
      testId="admin-users"
    >
      <form
        onSubmit={create}
        className="mb-3 flex flex-wrap items-end gap-2"
        aria-label="Create user"
      >
        <label className="flex flex-col text-xs text-bento-muted">
          Username
          <input
            value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value })}
            className={input}
          />
        </label>
        <label className="flex flex-col text-xs text-bento-muted">
          Role
          <select
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value as AdminUser['role'] })}
            className={input}
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col text-xs text-bento-muted">
          Initial password
          <input
            type="password"
            autoComplete="new-password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            className={input}
          />
        </label>
        <button
          type="submit"
          disabled={
            !form.username.trim() || !form.password || createProblems.length > 0 || action.isPending
          }
          className="rounded bg-sky-600 px-3 py-1 text-sm text-white hover:bg-sky-500 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-bento-muted"
        >
          Create user
        </button>
        {createProblems.length > 0 && (
          <span className="text-xs text-amber-700">Password needs {createProblems.join(', ')}</span>
        )}
      </form>
      {action.error && (
        <p role="alert" className="mb-2 text-sm text-red-700">
          {action.error.message}
        </p>
      )}
      {body}
    </Card>
  );
};
