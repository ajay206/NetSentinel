import type { Role } from './auth';

/**
 * Step 13b: what each role may do in the console. The gateway enforces the same rules (403),
 * so this only hides controls a role cannot use. Keep in sync with the handbook matrix.
 */
export const PERMISSIONS = {
  'dashboard.view': 'viewer',
  'runbooks.view': 'viewer',
  'copilot.analyze': 'operator',
  'incident.act': 'operator',
  'alarm.act': 'operator',
  // Step 16: anyone may read the approval queue; only operators decide
  'ticket.approve': 'operator',
  'admin.users': 'admin',
  'admin.audit': 'admin',
  'admin.settings': 'admin',
} as const satisfies Record<string, Role>;

export type Permission = keyof typeof PERMISSIONS;

const ORDER: Role[] = ['viewer', 'operator', 'admin'];

export function can(role: Role | undefined | null, permission: Permission): boolean {
  if (!role) return false;
  return ORDER.indexOf(role) >= ORDER.indexOf(PERMISSIONS[permission]);
}

export const ROLE_STYLE: Record<Role, string> = {
  viewer: 'bg-bento-bg text-navy ring-1 ring-bento-border',
  operator: 'bg-sky-500/15 text-sky-700 ring-1 ring-sky-500/40',
  admin: 'bg-amber-300 text-[#442900] ring-2 ring-amber-500/70 shadow-sm',
};

export const ROLE_BLURB: Record<Role, string> = {
  viewer: 'Read-only: dashboards, alarms, KPIs, incidents and runbooks.',
  operator:
    'Viewer + copilot, acknowledge / assign / resolve incidents and alarms, approve ticket drafts.',
  admin: 'Operator + user management, audit log and system settings.',
};
