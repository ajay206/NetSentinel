import React from 'react';
import { TIPS } from '../../lib/tooltips';
import { Card, StateMessage } from '../../components/ui/Card';
import { useAdminSettings } from '../../hooks/useAdmin';

/** Step 13b (admin): read-only auth/security settings (set via environment variables). */
export const SystemSettings: React.FC = () => {
  const s = useAdminSettings();
  let body: React.ReactNode;
  if (s.isLoading) body = <StateMessage kind="loading">Loading settings…</StateMessage>;
  else if (s.isError || !s.data)
    body = <StateMessage kind="error">Settings unavailable: {s.error?.message}</StateMessage>;
  else {
    const d = s.data;
    const rows: [string, React.ReactNode][] = [
      [
        'User store',
        d.userStore === 'postgres' ? 'TimescaleDB / Postgres' : 'In memory (dev only)',
      ],
      ['Token lifetime', `${Math.round((d.tokenTtlSeconds / 3600) * 10) / 10} h`],
      ['API rate limit', `${d.rateLimitPerMin} per user per minute`],
      ['Login rate limit', `${d.loginRateLimitPerMin} per IP per minute`],
      ['Lockout', `after ${d.lockoutThreshold} failed logins`],
      ['Lockout duration', `${Math.round(d.lockoutSeconds / 60)} min`],
      ['Demo users seeded', d.demoUsersSeeded ? 'Yes (change their passwords)' : 'No'],
      [
        'Auth disabled',
        d.authDisabled ? <span className="text-red-700">Yes — dev only</span> : 'No',
      ],
    ];
    body = (
      <dl
        className="grid grid-cols-1 gap-y-2 text-sm sm:grid-cols-[11rem_1fr] sm:gap-x-4"
        data-testid="settings-list"
      >
        {rows.map(([k, v]) => (
          <React.Fragment key={k}>
            <dt className="text-bento-muted">{k}</dt>
            <dd className="text-navy">{v}</dd>
          </React.Fragment>
        ))}
      </dl>
    );
  }
  return (
    <Card
      title="System & security settings"
      subtitle="Read-only view of auth settings; change them via environment variables."
      info={TIPS.panelSettings}
      testId="system-settings"
    >
      {body}
    </Card>
  );
};
