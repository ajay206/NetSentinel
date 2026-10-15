import { describe, expect, it } from 'vitest';
import { can, PERMISSIONS, type Permission } from './rbac';
import { passwordProblems, passwordStrength } from './passwordPolicy';

describe('rbac.can (Step 13b matrix)', () => {
  const expected: Record<Permission, [boolean, boolean, boolean]> = {
    'dashboard.view': [true, true, true],
    'runbooks.view': [true, true, true],
    'copilot.analyze': [false, true, true],
    'incident.act': [false, true, true],
    'alarm.act': [false, true, true],
    'ticket.approve': [false, true, true],
    'admin.users': [false, false, true],
    'admin.audit': [false, false, true],
    'admin.settings': [false, false, true],
  };
  it.each(Object.keys(PERMISSIONS) as Permission[])('%s', (perm) => {
    expect([can('viewer', perm), can('operator', perm), can('admin', perm)]).toEqual(
      expected[perm],
    );
  });
  it('denies without a role', () => {
    expect(can(undefined, 'dashboard.view')).toBe(false);
  });
});

describe('password policy mirrors the gateway', () => {
  it('lists unmet rules and scores strength', () => {
    expect(passwordProblems('N3w-Synthetic-pass!')).toEqual([]);
    expect(passwordProblems('short')).toContain('at least 10 characters');
    expect(passwordProblems('Ajay-Rocks-123!', 'ajay')).toContain('must not contain the username');
    expect(passwordProblems('Aa1!' + 'x'.repeat(69))).toContain('at most 72 bytes');
    expect(passwordStrength('')).toBe(0);
    expect(passwordStrength('N3w-Synthetic-pass!')).toBe(4);
  });
});
