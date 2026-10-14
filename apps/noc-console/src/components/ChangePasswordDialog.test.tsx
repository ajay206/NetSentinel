import { describe, expect, it, vi, afterEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ChangePasswordDialog } from './ChangePasswordDialog';

const STRONG = 'N3w-Synthetic-pass!';

function setup() {
  const onChanged = vi.fn();
  const onClose = vi.fn();
  render(<ChangePasswordDialog open username="viewer" onClose={onClose} onChanged={onChanged} />);
  const type = (label: string, value: string) =>
    fireEvent.change(screen.getByLabelText(label), { target: { value } });
  const submit = screen.getByRole('button', { name: 'Change password' });
  return { onChanged, onClose, type, submit };
}

describe('ChangePasswordDialog (13b)', () => {
  afterEach(() => vi.restoreAllMocks());

  it('enforces the policy, confirmation and difference before enabling submit', () => {
    const { type, submit } = setup();
    expect(submit).toBeDisabled();
    type('Current password', 'viewer');
    type('New password', 'weak');
    expect(screen.getByTestId('pw-problems')).toHaveTextContent('at least 10 characters');
    expect(screen.getByTestId('pw-strength')).toHaveTextContent('Too weak');
    type('New password', STRONG);
    expect(screen.queryByTestId('pw-problems')).toBeNull();
    expect(screen.getByTestId('pw-strength')).toHaveTextContent('Strong');
    type('Confirm new password', STRONG + 'x');
    expect(screen.getByText('Passwords do not match')).toBeInTheDocument();
    expect(submit).toBeDisabled();
    type('Confirm new password', STRONG);
    expect(submit).toBeEnabled();
  });

  it('posts the change and hands back the new token', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ accessToken: 't2', expiresIn: 60, username: 'viewer', role: 'viewer' }),
    });
    vi.stubGlobal('fetch', fetchMock);
    const { type, submit, onChanged, onClose } = setup();
    type('Current password', 'viewer');
    type('New password', STRONG);
    type('Confirm new password', STRONG);
    fireEvent.click(submit);
    await waitFor(() =>
      expect(onChanged).toHaveBeenCalledWith(expect.objectContaining({ accessToken: 't2' })),
    );
    expect(onClose).toHaveBeenCalled();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/auth/password');
    expect(JSON.parse(init.body)).toEqual({ currentPassword: 'viewer', newPassword: STRONG });
  });

  it('shows the server error (e.g. wrong current password)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        json: () => Promise.resolve({ detail: 'Current password is wrong' }),
      }),
    );
    const { type, submit, onChanged } = setup();
    type('Current password', 'nope');
    type('New password', STRONG);
    type('Confirm new password', STRONG);
    fireEvent.click(submit);
    expect(await screen.findByRole('alert')).toHaveTextContent('Current password is wrong');
    expect(onChanged).not.toHaveBeenCalled();
  });
});
