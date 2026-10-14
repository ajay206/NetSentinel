import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

export type AdminUser = {
  username: string;
  role: 'viewer' | 'operator' | 'admin';
  disabled: boolean;
  locked: boolean;
  failedLogins: number;
  createdAt: number;
  passwordChangedAt: number | null;
};

export type AuditEntry = {
  id: number;
  ts: number;
  actor: string;
  action: string;
  target: string;
  detail: Record<string, unknown>;
};

export type AdminSettings = {
  userStore: 'postgres' | 'memory';
  tokenTtlSeconds: number;
  rateLimitPerMin: number;
  loginRateLimitPerMin: number;
  lockoutThreshold: number;
  lockoutSeconds: number;
  demoUsersSeeded: boolean;
  authDisabled: boolean;
};

async function getJson<T>(url: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(url, init);
  const data: unknown = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const detail = (data as { detail?: unknown }).detail;
    throw new Error(typeof detail === 'string' ? detail : `Request failed (${resp.status})`);
  }
  return data as T;
}

export const useAdminUsers = () =>
  useQuery<AdminUser[], Error>({
    queryKey: ['admin', 'users'],
    queryFn: async () => (await getJson<{ items: AdminUser[] }>('/api/admin/users')).items,
  });

export const useAuditLog = (limit = 200) =>
  useQuery<AuditEntry[], Error>({
    queryKey: ['admin', 'audit', limit],
    queryFn: async () =>
      (await getJson<{ items: AuditEntry[] }>(`/api/admin/audit?limit=${limit}`)).items,
    refetchInterval: 15_000,
  });

export const useAdminSettings = () =>
  useQuery<AdminSettings, Error>({
    queryKey: ['admin', 'settings'],
    queryFn: () => getJson<AdminSettings>('/api/admin/settings'),
  });

type CreatePayload = {
  kind: 'create';
  username: string;
  role: AdminUser['role'];
  password: string;
};
type UpdatePayload = {
  kind: 'update';
  username: string;
  role?: AdminUser['role'];
  disabled?: boolean;
};
type UnlockPayload = { kind: 'unlock'; username: string };
type ResetPayload = { kind: 'reset'; username: string; newPassword: string };
export type AdminActionPayload = CreatePayload | UpdatePayload | UnlockPayload | ResetPayload;

function requestFor(p: AdminActionPayload): [string, RequestInit] {
  const base = `/api/admin/users`;
  const json = (method: string, body?: unknown): RequestInit => ({
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const user = `${base}/${encodeURIComponent(p.username)}`;
  switch (p.kind) {
    case 'create':
      return [base, json('POST', { username: p.username, role: p.role, password: p.password })];
    case 'update':
      return [user, json('PATCH', { role: p.role, disabled: p.disabled })];
    case 'unlock':
      return [`${user}/unlock`, json('POST')];
    case 'reset':
      return [`${user}/reset-password`, json('POST', { newPassword: p.newPassword })];
  }
}

export const useAdminUserAction = () => {
  const queryClient = useQueryClient();
  return useMutation<AdminUser, Error, AdminActionPayload>({
    mutationFn: (payload) => getJson<AdminUser>(...requestFor(payload)),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
      void queryClient.invalidateQueries({ queryKey: ['admin', 'audit'] });
    },
  });
};
